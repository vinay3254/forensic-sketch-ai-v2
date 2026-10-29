import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

interface Props {
  glb: ArrayBuffer | null
  heightCm: number
  preserveMaterials?: boolean
}

const PAPER = '#f4f1ea'
const GRAPHITE = '#2a2823'

function disposeObject(root: THREE.Object3D) {
  root.traverse((object) => {
    if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
      object.geometry.dispose()
      const materials = Array.isArray(object.material) ? object.material : [object.material]
      for (const material of materials) {
        for (const value of Object.values(material)) if (value instanceof THREE.Texture) value.dispose()
        material.dispose()
      }
    }
  })
}

// the Blender mannequin drawn like a pencil study: flat paper tones, graphite outlines, a height ruler
export default function FigureViewer({ glb, heightCm, preserveMaterials = false }: Props) {
  const [loadError, setLoadError] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const stage = useRef<{ scene: THREE.Scene; figure: THREE.Group; ruler: THREE.Group; render: () => void } | null>(null)

  useEffect(() => {
    const el = box.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(el.clientWidth, el.clientHeight)
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    scene.add(new THREE.HemisphereLight('#ffffff', '#b8b2a6', 2.4))
    const key = new THREE.DirectionalLight('#ffffff', 1.1)
    key.position.set(1.5, -3, 3)
    scene.add(key)
    // z is up in Blender's export once glTF converts it to y-up; a 2.4 m tall frame shows heights to scale
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 50)
    const frame = () => {
      const aspect = el.clientWidth / el.clientHeight
      const h = 2.4
      camera.left = (-h * aspect) / 2
      camera.right = (h * aspect) / 2
      // the camera looks level at the floor line; the frame runs from just below the feet to 2.35 m
      camera.top = h / 2
      camera.bottom = -h / 2
      camera.updateProjectionMatrix()
      renderer.setSize(el.clientWidth, el.clientHeight)
    }
    camera.position.set(0, 1.15, 8)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, 1.15, 0)
    controls.enablePan = false
    controls.enableZoom = true
    controls.minZoom = 0.7
    controls.maxZoom = 4
    controls.minPolarAngle = controls.maxPolarAngle = Math.PI / 2 // turn around, never tilt
    controls.update()
    frame()
    const figure = new THREE.Group()
    const ruler = new THREE.Group()
    scene.add(figure, ruler)
    const render = () => renderer.render(scene, camera)
    controls.addEventListener('change', render)
    const ro = new ResizeObserver(() => {
      frame()
      render()
    })
    ro.observe(el)
    stage.current = { scene, figure, ruler, render }
    render()
    return () => {
      ro.disconnect()
      controls.dispose()
      disposeObject(scene)
      renderer.dispose()
      el.removeChild(renderer.domElement)
      stage.current = null
    }
  }, [])

  // swap in each new model as it arrives
  useEffect(() => {
    const s = stage.current
    if (!s) return
    let cancelled = false
    const dispose = () => {
      disposeObject(s.figure)
      s.figure.clear()
    }
    if (!glb) { dispose(); s.render(); return }
    new GLTFLoader().parse(glb.slice(0), '', (gltf) => {
      if (cancelled) { disposeObject(gltf.scene); return }
      dispose()
      setLoadError(null)
      gltf.scene.traverse((o) => {
        if (!(o instanceof THREE.Mesh)) return
        if (preserveMaterials) {
          // a model painted with the drawings already carries their pencil shading: show it close to as drawn
          // (mostly self-lit) with a little scene light for shape, instead of a dull physically based material
          const old = o.material as THREE.MeshStandardMaterial
          if (old.map) {
            old.map.colorSpace = THREE.SRGBColorSpace
            o.material = new THREE.MeshLambertMaterial({ map: old.map, emissive: '#ffffff', emissiveMap: old.map, emissiveIntensity: 0.7, color: '#7a7a7a' })
            old.dispose()
          }
          return
        }
        const tone = (o.material as THREE.MeshStandardMaterial).color?.clone() ?? new THREE.Color(PAPER)
        o.material = new THREE.MeshLambertMaterial({ color: tone.lerp(new THREE.Color(PAPER), 0.25) })
        const lines = new THREE.LineSegments(new THREE.EdgesGeometry(o.geometry, 32), new THREE.LineBasicMaterial({ color: GRAPHITE }))
        o.add(lines)
      })
      s.figure.add(gltf.scene)
      s.render()
    }, (error) => {
      if (!cancelled) setLoadError(`Could not display this model: ${error instanceof Error ? error.message : 'invalid GLB'}`)
    })
    return () => { cancelled = true }
  }, [glb, preserveMaterials])

  // a ruler beside the figure, ticked every 10 cm up to the figure's height
  useEffect(() => {
    const s = stage.current
    if (!s) return
    disposeObject(s.ruler)
    s.ruler.clear()
    const h = heightCm / 100
    const pts: THREE.Vector3[] = [new THREE.Vector3(0.62, 0, 0), new THREE.Vector3(0.62, h, 0)]
    for (let cm = 0; cm <= heightCm; cm += 10) {
      const y = cm / 100
      const w = cm % 50 === 0 ? 0.05 : 0.025
      pts.push(new THREE.Vector3(0.62, y, 0), new THREE.Vector3(0.62 + w, y, 0))
    }
    pts.push(new THREE.Vector3(0.55, h, 0), new THREE.Vector3(0.69, h, 0))
    s.ruler.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: '#b0442c' })))
    s.render()
  }, [heightCm])

  return (
    <div className="relative h-full w-full">
      <div ref={box} className="h-full w-full cursor-grab" />
      {loadError && <p role="alert" className="absolute inset-x-3 bottom-3 rounded-xl bg-red-50 p-3 text-[13px] text-red-700">{loadError}</p>}
      <span className="pointer-events-none absolute right-3 top-3 rounded-full bg-white/80 px-2.5 py-1 font-mono text-[11px] text-accent">
        {Math.round(heightCm)} cm
      </span>
    </div>
  )
}
