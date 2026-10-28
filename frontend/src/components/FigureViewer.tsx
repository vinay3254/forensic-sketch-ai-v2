import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

interface Props {
  glb: ArrayBuffer | null
  heightCm: number
}

const PAPER = '#f4f1ea'
const GRAPHITE = '#2a2823'

// the Blender mannequin drawn like a pencil study: flat paper tones, graphite outlines, a height ruler
export default function FigureViewer({ glb, heightCm }: Props) {
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
      camera.top = h - 0.05
      camera.bottom = -0.05
      camera.updateProjectionMatrix()
      renderer.setSize(el.clientWidth, el.clientHeight)
    }
    camera.position.set(0, 0, 8)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.set(0, 0, 0) // turning only spins about the vertical axis, so aiming at the floor is fine
    controls.enablePan = false
    controls.enableZoom = false
    controls.minPolarAngle = controls.maxPolarAngle = Math.PI / 2 // turn around, never tilt
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
      renderer.dispose()
      el.removeChild(renderer.domElement)
      stage.current = null
    }
  }, [])

  // swap in each new model as it arrives
  useEffect(() => {
    const s = stage.current
    if (!s || !glb) return
    new GLTFLoader().parse(glb.slice(0), '', (gltf) => {
      s.figure.clear()
      gltf.scene.traverse((o) => {
        if (!(o instanceof THREE.Mesh)) return
        const tone = (o.material as THREE.MeshStandardMaterial).color?.clone() ?? new THREE.Color(PAPER)
        o.material = new THREE.MeshLambertMaterial({ color: tone.lerp(new THREE.Color(PAPER), 0.25) })
        const lines = new THREE.LineSegments(new THREE.EdgesGeometry(o.geometry, 32), new THREE.LineBasicMaterial({ color: GRAPHITE }))
        o.add(lines)
      })
      s.figure.add(gltf.scene)
      s.render()
    })
  }, [glb])

  // a ruler beside the figure, ticked every 10 cm up to the figure's height
  useEffect(() => {
    const s = stage.current
    if (!s) return
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
      <span className="pointer-events-none absolute right-3 top-3 rounded-full bg-white/80 px-2.5 py-1 font-mono text-[11px] text-accent">
        {Math.round(heightCm)} cm
      </span>
    </div>
  )
}
