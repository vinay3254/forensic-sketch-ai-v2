import { useCallback, useEffect, useRef, useState } from 'react'

// Minimal typing for the Web Speech API (Chrome/Edge ship it prefixed as webkitSpeechRecognition).
interface RecognitionResult {
  isFinal: boolean
  0: { transcript: string }
}
interface RecognitionEvent {
  resultIndex: number
  results: ArrayLike<RecognitionResult>
}
interface Recognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: RecognitionEvent) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
type RecognitionCtor = new () => Recognition

const Ctor: RecognitionCtor | undefined =
  typeof window === 'undefined'
    ? undefined
    : ((window as unknown as Record<string, RecognitionCtor | undefined>).SpeechRecognition ??
      (window as unknown as Record<string, RecognitionCtor | undefined>).webkitSpeechRecognition)

export const speechSupported = !!Ctor

const ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone permission was denied. Allow it in the browser to dictate.',
  'service-not-allowed': 'Microphone permission was denied. Allow it in the browser to dictate.',
  'audio-capture': 'No microphone was found.',
  network: 'Speech recognition needs an internet connection.',
}

/**
 * Dictation that hands each finished phrase to `onFinal` exactly as recognised.
 * Words still being recognised are exposed as `interim` and never saved.
 */
export function useSpeech(lang: string, onFinal: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState<string | null>(null)
  const rec = useRef<Recognition | null>(null)
  const finalRef = useRef(onFinal)
  useEffect(() => {
    finalRef.current = onFinal
  }, [onFinal])

  const stop = useCallback(() => {
    rec.current?.stop()
  }, [])

  const start = useCallback(() => {
    if (!Ctor) return
    setError(null)
    const r = new Ctor()
    r.lang = lang
    r.continuous = true
    r.interimResults = true
    r.onresult = (e) => {
      let pending = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i]
        const phrase = res[0].transcript.trim()
        if (res.isFinal) {
          if (phrase) finalRef.current(phrase) // Chrome sometimes finalises silence as ""
        } else pending += res[0].transcript
      }
      setInterim(pending)
    }
    r.onerror = (e) => {
      if (e.error !== 'no-speech' && e.error !== 'aborted') setError(ERRORS[e.error] ?? `Speech recognition failed (${e.error}).`)
    }
    r.onend = () => {
      setListening(false)
      setInterim('')
      rec.current = null
    }
    rec.current = r
    r.start()
    setListening(true)
  }, [lang])

  // never keep the microphone open after leaving the question, and drop any late results
  useEffect(
    () => () => {
      if (rec.current) rec.current.onresult = null
      rec.current?.stop()
    },
    [],
  )

  return { listening, interim, error, start, stop }
}
