import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

export interface ViewerApi {
  setYaw: (deg: number) => void
  getYaw: () => number
  capture: () => string // PNG data URL of the current view
}

interface Props {
  meshUrl: string
  onReady: (api: ViewerApi | null) => void
}

const DEG = Math.PI / 180

// yaw is from the witness's side: -90 = the person's left profile, +90 = right profile.
// The head faces +z and the person's left is +x, so yaw is minus the camera's azimuth.
export default function HeadViewer({ meshUrl, onReady }: Props) {
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = box.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(el.clientWidth, el.clientHeight)
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#ffffff')
    scene.add(new THREE.HemisphereLight('#ffffff', '#888888', 2.2))
    const key = new THREE.DirectionalLight('#ffffff', 1.2)
    scene.add(key)
    const camera = new THREE.PerspectiveCamera(30, el.clientWidth / el.clientHeight, 0.01, 100)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enablePan = false
    controls.minAzimuthAngle = -90 * DEG
    controls.maxAzimuthAngle = 90 * DEG
    controls.minPolarAngle = 70 * DEG
    controls.maxPolarAngle = 110 * DEG
    let distance = 3

    const placeCamera = (azimuth: number) => {
      const t = controls.target
      camera.position.set(t.x + distance * Math.sin(azimuth), t.y, t.z + distance * Math.cos(azimuth))
      controls.update()
    }

    let frame = 0
    const loop = () => {
      key.position.copy(camera.position) // light follows the camera so every side reads clearly
      renderer.render(scene, camera)
      frame = requestAnimationFrame(loop)
    }

    let disposed = false
    new GLTFLoader().load(meshUrl, (gltf) => {
      if (disposed) return
      const model = gltf.scene
      const bounds = new THREE.Box3().setFromObject(model)
      const size = bounds.getSize(new THREE.Vector3())
      controls.target.copy(bounds.getCenter(new THREE.Vector3()))
      distance = (Math.max(size.x, size.y) / 2 / Math.tan((camera.fov / 2) * DEG)) * 1.25
      controls.minDistance = distance * 0.6
      controls.maxDistance = distance * 1.6
      scene.add(model)
      placeCamera(0)
      onReady({
        setYaw: (deg) => placeCamera(-deg * DEG),
        getYaw: () => Math.round(-controls.getAzimuthalAngle() / DEG),
        capture: () => {
          renderer.render(scene, camera)
          return renderer.domElement.toDataURL('image/png')
        },
      })
    })
    loop()

    return () => {
      disposed = true
      onReady(null)
      cancelAnimationFrame(frame)
      controls.dispose()
      renderer.dispose()
      el.removeChild(renderer.domElement)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meshUrl])

  return <div ref={box} className="aspect-[3/4] w-full max-w-sm cursor-grab rounded border bg-white" />
}
