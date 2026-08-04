"use client";
// Login mínimo de un campo (A5): pide el token una vez y lo guarda en el dispositivo.
import { useState } from "react";
import { setToken } from "@/lib/api";

export default function TokenGate({ onDone }: { onDone: () => void }) {
  const [value, setValue] = useState("");
  return (
    <main>
      <h1>listenyourPDFs</h1>
      <div className="card">
        <h2>Acceso</h2>
        <p className="muted">
          Introduce el token de tu instancia (variable LYP_TOKEN del servidor).
          Se guarda en este dispositivo.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setToken(value.trim());
            onDone();
          }}
        >
          <input
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="token"
            aria-label="token"
          />
          <button className="btn btn-primary btn-xl" style={{ marginTop: "0.8rem" }}>
            Entrar
          </button>
        </form>
      </div>
    </main>
  );
}
