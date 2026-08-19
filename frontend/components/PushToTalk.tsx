"use client";
// Push-to-talk (RF-4.1): mantén pulsado → graba → suelta → el tutor responde en voz.
// La respuesta llega por WS en frases (sentence.audio) que se encadenan según llegan
// (pipeline L3); al terminar, el reproductor retoma exactamente donde estaba.
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, getToken, mediaUrl } from "@/lib/api";

export type TutorEvent =
  | { type: "answer.delta"; request_id: string; text: string }
  | { type: "sentence.audio"; request_id: string; idx: number; url: string }
  | { type: "answer.done"; request_id: string; first_audio_ms?: number }
  | { type: "answer.error"; request_id: string; error: string };

type Phase = "idle" | "recording" | "thinking" | "speaking";

export default function PushToTalk({
  docId,
  blockId,
  subscribe,
  onStart,
  onFinish,
}: {
  docId: number;
  blockId: number | undefined;
  /** Suscripción a eventos del WS del documento; devuelve unsubscribe. */
  subscribe: (handler: (ev: TutorEvent) => void) => () => void;
  /** Pausa el reproductor principal antes de hablar. */
  onStart: () => void;
  /** Retoma el reproductor al acabar la respuesta. */
  onFinish: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [answerText, setAnswerText] = useState("");
  const [transcript, setTranscript] = useState("");
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const requestRef = useRef<string>("");
  const queueRef = useRef<string[]>([]);
  const nextIdxRef = useRef(0);
  const doneRef = useRef(false);
  const voiceRef = useRef<HTMLAudioElement | null>(null);

  const playNext = useCallback(() => {
    const url = queueRef.current.shift();
    if (url) {
      setPhase("speaking");
      const a = voiceRef.current!;
      a.src = url;
      a.play().catch(() => finishAll());
      return;
    }
    if (doneRef.current) finishAll();
    // si no hay done aún, esperamos al siguiente sentence.audio
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const finishAll = useCallback(() => {
    setPhase("idle");
    onFinish();
  }, [onFinish]);

  useEffect(() => {
    const unsub = subscribe((ev) => {
      if (!("request_id" in ev) || ev.request_id !== requestRef.current) return;
      if (ev.type === "answer.delta") {
        setAnswerText((t) => t + ev.text);
      } else if (ev.type === "sentence.audio") {
        queueRef.current.push(mediaUrl(ev.url));
        const a = voiceRef.current;
        if (a && (a.paused || a.ended) && phaseRef.current !== "speaking") playNext();
      } else if (ev.type === "answer.done") {
        doneRef.current = true;
        const a = voiceRef.current;
        if (a && (a.paused || a.ended) && queueRef.current.length === 0) finishAll();
      } else if (ev.type === "answer.error") {
        setAnswerText(`⚠️ ${ev.error}`);
        finishAll();
      }
    });
    return unsub;
  }, [subscribe, playNext, finishAll]);

  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  async function startRecording() {
    if (phase !== "idle" || !blockId) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      onStart(); // pausa la narración
      setAnswerText("");
      setTranscript("");
      chunksRef.current = [];
      const rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        sendQuestion(new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" }));
      };
      recRef.current = rec;
      rec.start();
      setPhase("recording");
    } catch {
      setAnswerText("⚠️ No hay acceso al micrófono (revisa permisos y HTTPS)");
    }
  }

  function stopRecording() {
    if (phase === "recording") recRef.current?.stop();
  }

  async function sendQuestion(audio: Blob) {
    setPhase("thinking");
    doneRef.current = false;
    queueRef.current = [];
    nextIdxRef.current = 0;
    const body = new FormData();
    body.append("audio", audio, "question.webm");
    body.append("block_id", String(blockId));
    try {
      const res = await fetch(`${API_BASE}/api/documents/${docId}/ask`, {
        method: "POST",
        body,
        headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();
      requestRef.current = data.request_id;
      if (data.transcript) setTranscript(data.transcript);
    } catch {
      setAnswerText("⚠️ No se pudo enviar la pregunta");
      finishAll();
    }
  }

  return (
    <div className="card">
      <button
        className="btn btn-primary btn-xl"
        data-testid="ptt-button"
        style={phase === "recording" ? { background: "var(--warn)", borderColor: "var(--warn)" } : {}}
        onPointerDown={startRecording}
        onPointerUp={stopRecording}
        onPointerLeave={stopRecording}
        onKeyDown={(e) => e.key === " " && startRecording()}
        onKeyUp={(e) => e.key === " " && stopRecording()}
        disabled={phase === "thinking" || phase === "speaking"}
      >
        {phase === "recording" && "🔴 Suelta para preguntar"}
        {phase === "thinking" && "🤔 Pensando…"}
        {phase === "speaking" && "🗣️ Respondiendo…"}
        {phase === "idle" && "🎙️ Mantén pulsado y pregunta"}
      </button>
      {transcript && <p className="muted" data-testid="ptt-transcript">«{transcript}»</p>}
      {answerText && <p className="block-text" data-testid="ptt-answer">{answerText}</p>}
      <audio ref={voiceRef} data-testid="ptt-voice" onEnded={playNext} />
    </div>
  );
}
