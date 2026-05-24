from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - handled at runtime for friendly setup.
    load_dotenv = None

from moses import DEFAULT_MODEL, DEFAULT_TIMEZONE, SYSTEM_INSTRUCTION, AssistantStore, MosesAgent, WorkspaceAccess


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MOSES Command Center</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #05070b;
      --panel: rgba(8, 15, 22, 0.86);
      --panel-strong: rgba(11, 24, 34, 0.96);
      --line: rgba(92, 220, 255, 0.28);
      --line-strong: rgba(92, 220, 255, 0.58);
      --cyan: #5cddff;
      --mint: #6fffc3;
      --amber: #ffd166;
      --red: #ff6b6b;
      --text: #e9fbff;
      --muted: #8fb2bf;
      --shadow: 0 20px 80px rgba(0, 0, 0, 0.45);
      font-family: Inter, "Segoe UI", Roboto, Arial, sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        radial-gradient(circle at 20% 20%, rgba(92, 221, 255, 0.12), transparent 28rem),
        radial-gradient(circle at 80% 8%, rgba(111, 255, 195, 0.08), transparent 24rem),
        linear-gradient(135deg, #040509 0%, #07101a 45%, #05080d 100%);
      overflow: hidden;
    }

    html,
    body {
      max-width: 100%;
    }

    .scanlines {
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: 0.16;
      background: repeating-linear-gradient(
        to bottom,
        transparent 0,
        transparent 6px,
        rgba(92, 220, 255, 0.08) 7px
      );
      mix-blend-mode: screen;
    }

    .shell {
      height: 100vh;
      width: 100%;
      display: grid;
      grid-template-columns: minmax(240px, 300px) minmax(420px, 1fr) minmax(250px, 330px);
      gap: 16px;
      padding: 16px;
    }

    .panel {
      min-width: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }

    .sidebar,
    .intel {
      display: flex;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
    }

    .brand {
      padding: 18px;
      border-bottom: 1px solid var(--line);
    }

    .brand h1,
    .section-title,
    .status-title {
      margin: 0;
      letter-spacing: 0;
      font-weight: 700;
    }

    .brand h1 {
      font-size: 28px;
      line-height: 1;
    }

    .brand p,
    .status-copy,
    .item-meta,
    .empty {
      color: var(--muted);
    }

    .brand p {
      margin: 8px 0 0;
      font-size: 13px;
      line-height: 1.45;
    }

    .core-wrap {
      position: relative;
      display: grid;
      place-items: center;
      min-height: 260px;
      border-bottom: 1px solid var(--line);
    }

    #core {
      width: min(86%, 250px);
      aspect-ratio: 1;
    }

    .core-label {
      position: absolute;
      display: grid;
      place-items: center;
      width: 120px;
      height: 120px;
      border: 1px solid var(--line-strong);
      border-radius: 50%;
      background: rgba(4, 11, 18, 0.72);
      box-shadow: 0 0 32px rgba(92, 221, 255, 0.2);
      text-align: center;
      font-size: 12px;
      color: var(--muted);
    }

    .core-label strong {
      display: block;
      color: var(--text);
      font-size: 19px;
      line-height: 1.25;
      margin-bottom: 4px;
    }

    .metrics {
      display: grid;
      gap: 10px;
      padding: 14px;
      border-bottom: 1px solid var(--line);
    }

    .metric {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border: 1px solid rgba(92, 220, 255, 0.16);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.03);
      font-size: 13px;
    }

    .metric strong {
      color: var(--cyan);
      font-size: 18px;
    }

    .vision {
      padding: 14px;
      display: grid;
      gap: 10px;
    }

    .vision-frame {
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(92, 220, 255, 0.2);
      border-radius: 8px;
      aspect-ratio: 16 / 10;
      background:
        linear-gradient(135deg, rgba(92, 220, 255, 0.08), rgba(111, 255, 195, 0.04)),
        rgba(0, 0, 0, 0.2);
    }

    #visionPreview {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
      background: rgba(2, 7, 12, 0.88);
    }

    .vision-empty {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      color: var(--muted);
      font-size: 12px;
      text-align: center;
      padding: 14px;
      pointer-events: none;
    }

    .vision-live .vision-empty {
      display: none;
    }

    .vision-actions {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }

    .vision-actions button {
      min-height: 34px;
      font-size: 12px;
      padding: 0 8px;
    }

    .vision-status {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }

    .main {
      display: grid;
      grid-template-rows: auto 1fr auto;
      min-height: 0;
      overflow: hidden;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(90deg, rgba(92, 220, 255, 0.1), rgba(111, 255, 195, 0.04));
    }

    .status-title {
      font-size: 15px;
    }

    .status-copy {
      margin-top: 4px;
      font-size: 12px;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }

    button {
      min-width: 0;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--text);
      background: rgba(92, 220, 255, 0.08);
      cursor: pointer;
      font: inherit;
      transition: border-color 140ms ease, background 140ms ease, transform 140ms ease;
    }

    button:hover {
      border-color: var(--line-strong);
      background: rgba(92, 220, 255, 0.14);
    }

    button:active {
      transform: translateY(1px);
    }

    .icon-btn {
      width: 42px;
      padding: 0;
      display: grid;
      place-items: center;
      font-size: 16px;
    }

    .text-btn {
      padding: 0 12px;
      font-size: 13px;
    }

    #coworkBtn {
      min-width: 76px;
    }

    .cowork-on #coworkBtn {
      color: #001116;
      background: linear-gradient(135deg, var(--amber), var(--mint));
      border-color: transparent;
      font-weight: 700;
    }

    .messages {
      min-height: 0;
      overflow-y: auto;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      scrollbar-color: rgba(92, 220, 255, 0.5) transparent;
    }

    .message {
      max-width: min(760px, 88%);
      padding: 12px 14px;
      border-radius: 8px;
      border: 1px solid rgba(92, 220, 255, 0.16);
      line-height: 1.5;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .message.user {
      align-self: flex-end;
      background: rgba(92, 220, 255, 0.12);
      border-color: rgba(92, 220, 255, 0.35);
    }

    .message.assistant {
      align-self: flex-start;
      background: rgba(111, 255, 195, 0.08);
      border-color: rgba(111, 255, 195, 0.22);
    }

    .message.system {
      align-self: center;
      max-width: 720px;
      background: rgba(255, 209, 102, 0.08);
      border-color: rgba(255, 209, 102, 0.22);
      color: #ffe7a6;
      font-size: 13px;
    }

    .composer {
      border-top: 1px solid var(--line);
      padding: 14px;
      background: rgba(5, 10, 15, 0.72);
    }

    .quick {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 10px;
    }

    .quick button {
      flex: 0 0 auto;
      min-height: 34px;
      padding: 0 10px;
      font-size: 12px;
      color: var(--muted);
    }

    .input-row {
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 10px;
      align-items: end;
    }

    textarea {
      width: 100%;
      min-width: 0;
      min-height: 50px;
      max-height: 150px;
      resize: vertical;
      padding: 13px 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--text);
      background: rgba(2, 7, 12, 0.88);
      outline: none;
      font: inherit;
      line-height: 1.4;
    }

    textarea:focus {
      border-color: var(--line-strong);
      box-shadow: 0 0 0 3px rgba(92, 220, 255, 0.1);
    }

    .send {
      width: 52px;
      height: 50px;
      color: #001116;
      background: linear-gradient(135deg, var(--cyan), var(--mint));
      border-color: transparent;
      font-size: 20px;
      font-weight: 800;
    }

    .intel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }

    .section-title {
      font-size: 14px;
    }

    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding: 10px;
      border-bottom: 1px solid var(--line);
    }

    .tabs button {
      flex: 1 1 62px;
      min-height: 34px;
      font-size: 12px;
      padding: 0 6px;
    }

    .tabs button.active {
      color: #001116;
      background: var(--cyan);
      border-color: transparent;
    }

    .list {
      min-height: 0;
      overflow-y: auto;
      padding: 12px;
      display: grid;
      gap: 10px;
    }

    .item {
      padding: 11px;
      border: 1px solid rgba(92, 220, 255, 0.16);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.03);
    }

    .item-title {
      font-size: 13px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }

    .item-meta {
      margin-top: 6px;
      font-size: 11px;
      line-height: 1.35;
    }

    .item-diff {
      max-height: 180px;
      overflow: auto;
      margin: 10px 0 0;
      padding: 10px;
      border: 1px solid rgba(92, 220, 255, 0.16);
      border-radius: 8px;
      background: rgba(0, 0, 0, 0.28);
      color: #c7f3ff;
      font-family: Consolas, "Courier New", monospace;
      font-size: 11px;
      line-height: 1.45;
      white-space: pre;
    }

    .item-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 10px;
    }

    .item-actions button {
      min-height: 32px;
      font-size: 12px;
    }

    .apply-btn {
      color: #001116;
      background: var(--mint);
      border-color: transparent;
    }

    .reject-btn {
      border-color: rgba(255, 107, 107, 0.35);
      color: #ffd6d6;
    }

    .empty {
      padding: 18px 8px;
      text-align: center;
      font-size: 13px;
      line-height: 1.45;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 0 8px;
      border: 1px solid rgba(92, 220, 255, 0.24);
      border-radius: 999px;
      color: var(--cyan);
      font-size: 11px;
      margin-top: 8px;
    }

    .busy .send {
      opacity: 0.7;
      pointer-events: none;
    }

    @media (max-width: 1020px) {
      body {
        overflow: auto;
      }

      .shell {
        min-height: 100vh;
        height: auto;
        grid-template-columns: minmax(0, 1fr);
      }

      .core-wrap {
        min-height: 210px;
      }

      .main {
        min-height: 68vh;
      }
    }

    @media (max-width: 620px) {
      .shell {
        padding: 10px;
        gap: 10px;
        overflow-x: hidden;
      }

      .panel,
      .main,
      .sidebar,
      .intel,
      .topbar,
      .composer,
      .messages {
        width: 100%;
        max-width: 100%;
        min-width: 0;
        overflow-x: hidden;
      }

      .topbar {
        flex-direction: column;
        align-items: stretch;
      }

      .actions {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        justify-content: stretch;
        width: 100%;
        min-width: 0;
      }

      .status-copy,
      .status-title {
        overflow-wrap: anywhere;
      }

      .message {
        max-width: 100%;
        width: 100%;
      }

      .input-row {
        display: grid;
      }

      .input-row {
        grid-template-columns: 1fr;
      }

      .send,
      .icon-btn,
      .text-btn {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <div class="scanlines"></div>
  <main class="shell">
    <aside class="panel sidebar">
      <section class="brand">
        <h1>MOSES</h1>
        <p>Personal assistant command center</p>
      </section>
      <section class="core-wrap" aria-label="MOSES system core">
        <canvas id="core" width="500" height="500"></canvas>
        <div class="core-label">
          <div><strong id="coreState">ONLINE</strong><span id="coreSub">standing by</span></div>
        </div>
      </section>
      <section class="metrics" aria-label="assistant metrics">
        <div class="metric"><span>Memory</span><strong id="memoryCount">0</strong></div>
        <div class="metric"><span>Todos</span><strong id="todoCount">0</strong></div>
        <div class="metric"><span>Reminders</span><strong id="reminderCount">0</strong></div>
      </section>
      <section class="vision" aria-label="computer vision">
        <div class="vision-frame" id="visionFrame">
          <video id="visionPreview" autoplay muted playsinline></video>
          <div class="vision-empty" id="visionEmpty">Camera or screen vision</div>
        </div>
        <div class="vision-actions">
          <button type="button" id="cameraBtn">Camera</button>
          <button type="button" id="screenBtn">Screen</button>
          <button type="button" id="stopVisionBtn">Stop</button>
        </div>
        <div class="vision-status" id="visionStatus">Vision is off.</div>
      </section>
    </aside>

    <section class="panel main" aria-label="chat">
      <header class="topbar">
        <div>
          <div class="status-title" id="statusTitle">Ready for command</div>
          <div class="status-copy" id="statusCopy">Ask MOSES to plan, remember, calculate, or organize.</div>
        </div>
        <div class="actions">
          <button class="icon-btn" id="voiceBtn" title="Start voice input" aria-label="Start voice input">MIC</button>
          <button class="icon-btn" id="speakBtn" title="Toggle spoken replies" aria-label="Toggle spoken replies">VOL</button>
          <button class="icon-btn" id="visionAskBtn" title="Analyze camera or screen" aria-label="Analyze camera or screen">EYE</button>
          <button class="text-btn" id="coworkBtn" title="Toggle Cowork mode" aria-label="Toggle Cowork mode">Cowork</button>
          <button class="text-btn" id="refreshBtn">Refresh</button>
        </div>
      </header>
      <section class="messages" id="messages" aria-live="polite"></section>
      <form class="composer" id="composer">
        <div class="quick" aria-label="quick prompts">
          <button type="button" data-prompt="What should I focus on today?">Daily focus</button>
          <button type="button" data-prompt="List my open todos.">Open todos</button>
          <button type="button" data-prompt="What do you see right now?">Analyze view</button>
          <button type="button" data-prompt="Remember that I prefer direct and practical answers.">Remember style</button>
          <button type="button" data-prompt="Create a note titled Ideas with three useful project ideas.">Create note</button>
        </div>
        <div class="input-row">
          <textarea id="prompt" placeholder="Speak or type your command..." autocomplete="off"></textarea>
          <button class="icon-btn" type="button" id="clearBtn" title="Clear input" aria-label="Clear input">CLR</button>
          <button class="send" type="submit" title="Send command" aria-label="Send command">></button>
        </div>
      </form>
    </section>

    <aside class="panel intel">
      <header class="intel-header">
        <h2 class="section-title">Local Intel</h2>
        <div style="display: flex; gap: 6px; align-items: center;">
          <select id="backendSelect" class="pill" style="background: transparent; outline: none; cursor: pointer; border-color: rgba(92, 220, 255, 0.4); margin-top: 0;">
            <option value="gemini" style="background: #080f16; color: var(--cyan);">Gemini</option>
            <option value="ollama" style="background: #080f16; color: var(--cyan);">Ollama</option>
            <option value="gptoss" style="background: #080f16; color: var(--cyan);">GPT-OSS</option>
          </select>
          <span class="pill" id="modelName" style="margin-top: 0;">Gemini</span>
        </div>
      </header>
      <nav class="tabs" aria-label="local state tabs">
        <button class="active" data-tab="todos">Todos</button>
        <button data-tab="reminders">Reminders</button>
        <button data-tab="memory">Memory</button>
        <button data-tab="notes">Notes</button>
        <button data-tab="changes">Changes</button>
      </nav>
      <section class="list" id="intelList"></section>
    </aside>
  </main>

  <script>
    const state = {
      busy: false,
      tab: "todos",
      speaking: false,
      coworkEnabled: false,
      visionMode: "none",
      visionStream: null,
      data: { memory: [], todos: [], reminders: [], notes: [], pending_changes: [], model: "" }
    };

    const el = {
      body: document.body,
      messages: document.getElementById("messages"),
      prompt: document.getElementById("prompt"),
      composer: document.getElementById("composer"),
      statusTitle: document.getElementById("statusTitle"),
      statusCopy: document.getElementById("statusCopy"),
      coreState: document.getElementById("coreState"),
      coreSub: document.getElementById("coreSub"),
      intelList: document.getElementById("intelList"),
      memoryCount: document.getElementById("memoryCount"),
      todoCount: document.getElementById("todoCount"),
      reminderCount: document.getElementById("reminderCount"),
      modelName: document.getElementById("modelName"),
      backendSelect: document.getElementById("backendSelect"),
      voiceBtn: document.getElementById("voiceBtn"),
      speakBtn: document.getElementById("speakBtn"),
      visionAskBtn: document.getElementById("visionAskBtn"),
      coworkBtn: document.getElementById("coworkBtn"),
      visionPreview: document.getElementById("visionPreview"),
      visionFrame: document.getElementById("visionFrame"),
      visionStatus: document.getElementById("visionStatus")
    };

    function addMessage(role, text) {
      const node = document.createElement("div");
      node.className = "message " + role;
      node.textContent = text;
      el.messages.appendChild(node);
      el.messages.scrollTop = el.messages.scrollHeight;
    }

    function setBusy(nextBusy) {
      state.busy = nextBusy;
      el.body.classList.toggle("busy", nextBusy);
      el.coreState.textContent = nextBusy ? "THINKING" : "ONLINE";
      el.coreSub.textContent = nextBusy ? "processing" : "standing by";
      if (nextBusy) {
        el.statusTitle.textContent = "Processing command";
        el.statusCopy.textContent = "MOSES is using its tools when needed.";
      } else {
        renderCoworkMode();
      }
    }

    async function sendPrompt(text) {
      const prompt = text.trim();
      if (!prompt || state.busy) return;
      addMessage("user", prompt);
      el.prompt.value = "";
      setBusy(true);

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: prompt, backend: el.backendSelect.value })
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "MOSES could not complete the command.");
        }
        addMessage("assistant", payload.reply);
        speak(payload.reply);
        await loadState();
      } catch (error) {
        addMessage("system", error.message);
      } finally {
        setBusy(false);
      }
    }

    async function sendVisionPrompt(text) {
      const prompt = text.trim() || "What do you see right now?";
      if (state.busy) return;
      const image = captureVisionFrame();
      if (!image) {
        addMessage("system", "Start Camera or Screen vision first.");
        return;
      }

      addMessage("user", prompt + " [vision]");
      el.prompt.value = "";
      setBusy(true);

      try {
        const response = await fetch("/api/vision", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: prompt, image, backend: el.backendSelect.value })
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "MOSES could not analyze the visual input.");
        }
        addMessage("assistant", payload.reply);
        speak(payload.reply);
        await loadState();
      } catch (error) {
        addMessage("system", error.message);
      } finally {
        setBusy(false);
      }
    }

    async function loadState() {
      try {
        const response = await fetch("/api/state");
        const payload = await response.json();
        state.data = payload;
        state.coworkEnabled = Boolean(payload.cowork_enabled);
        state.data.pending_changes = payload.pending_changes || [];
        renderState();
        renderCoworkMode();
      } catch (error) {
        addMessage("system", "Could not load local assistant state.");
      }
    }

    async function setCoworkMode(enabled) {
      try {
        const response = await fetch("/api/cowork", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled })
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "Could not toggle Cowork mode.");
        }
        state.coworkEnabled = Boolean(payload.cowork_enabled);
        renderCoworkMode();
        addMessage("system", state.coworkEnabled
          ? "Cowork mode enabled. MOSES will stage safe workspace edits in the Changes tab."
          : "Cowork mode disabled. MOSES can still read and advise, but file changes are blocked.");
      } catch (error) {
        addMessage("system", error.message);
      }
    }

    function renderCoworkMode() {
      el.body.classList.toggle("cowork-on", state.coworkEnabled);
      el.coworkBtn.textContent = state.coworkEnabled ? "Cowork ON" : "Cowork";
      if (!state.busy) {
        el.statusTitle.textContent = state.coworkEnabled ? "Cowork mode active" : "Ready for command";
        el.statusCopy.textContent = state.coworkEnabled
          ? "MOSES stages safe file edits for review in Changes."
          : "Ask MOSES to plan, remember, calculate, analyze, or organize.";
      }
    }

    async function handleChange(changeId, action) {
      try {
        const response = await fetch("/api/cowork-change", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: changeId, action })
        });
        const payload = await response.json();
        if (!response.ok || payload.error) {
          throw new Error(payload.error || "Could not update the change.");
        }
        addMessage("system", action === "apply"
          ? `Applied ${changeId} to ${payload.path}.`
          : `Rejected ${changeId}.`);
        await loadState();
      } catch (error) {
        addMessage("system", error.message);
      }
    }

    function renderState() {
      const openTodos = state.data.todos.filter((item) => item.status === "open");
      const openReminders = state.data.reminders.filter((item) => item.status === "open");
      el.memoryCount.textContent = state.data.memory.length;
      el.todoCount.textContent = openTodos.length;
      el.reminderCount.textContent = openReminders.length;
      el.modelName.textContent = state.data.model || "Gemini";

      const records = {
        todos: openTodos,
        reminders: openReminders,
        memory: state.data.memory,
        notes: state.data.notes.slice(-12).reverse(),
        changes: state.data.pending_changes || []
      }[state.tab] || [];

      el.intelList.replaceChildren();
      if (!records.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "No local records yet.";
        el.intelList.appendChild(empty);
        return;
      }

      for (const record of records) {
        el.intelList.appendChild(renderRecord(record));
      }
    }

    function renderRecord(record) {
      const node = document.createElement("article");
      node.className = "item";

      const title = document.createElement("div");
      title.className = "item-title";
      title.textContent = record.task || record.text || record.title || record.key || record.path || record.id;
      node.appendChild(title);

      if (record.value || record.body) {
        const body = document.createElement("div");
        body.className = "item-meta";
        body.textContent = record.value || record.body;
        node.appendChild(body);
      }

      const meta = document.createElement("div");
      meta.className = "item-meta";
      const bits = [record.id, record.action, record.priority, record.due, record.remind_at, record.status].filter(Boolean);
      meta.textContent = bits.join(" | ");
      node.appendChild(meta);

      if (record.diff) {
        const diff = document.createElement("pre");
        diff.className = "item-diff";
        diff.textContent = record.diff;
        node.appendChild(diff);
      }

      if (record.id && record.id.startsWith("change-")) {
        const actions = document.createElement("div");
        actions.className = "item-actions";
        const apply = document.createElement("button");
        apply.className = "apply-btn";
        apply.type = "button";
        apply.textContent = "Apply";
        apply.addEventListener("click", () => handleChange(record.id, "apply"));
        const reject = document.createElement("button");
        reject.className = "reject-btn";
        reject.type = "button";
        reject.textContent = "Reject";
        reject.addEventListener("click", () => handleChange(record.id, "reject"));
        actions.append(apply, reject);
        node.appendChild(actions);
      }
      return node;
    }

    function speak(text) {
      if (!state.speaking || !("speechSynthesis" in window)) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1;
      utterance.pitch = 0.92;
      window.speechSynthesis.speak(utterance);
    }

    async function startVision(mode) {
      stopVision();
      try {
        const stream = mode === "screen"
          ? await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false })
          : await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        state.visionStream = stream;
        state.visionMode = mode;
        el.visionPreview.srcObject = stream;
        el.visionFrame.classList.add("vision-live");
        el.visionStatus.textContent = mode === "screen" ? "Screen vision is active." : "Camera vision is active.";
        stream.getVideoTracks()[0].addEventListener("ended", stopVision);
      } catch (error) {
        state.visionMode = "none";
        el.visionStatus.textContent = "Vision permission was not granted.";
        addMessage("system", "Vision could not start: " + error.message);
      }
    }

    function stopVision() {
      if (state.visionStream) {
        state.visionStream.getTracks().forEach((track) => track.stop());
      }
      state.visionStream = null;
      state.visionMode = "none";
      el.visionPreview.srcObject = null;
      el.visionFrame.classList.remove("vision-live");
      el.visionStatus.textContent = "Vision is off.";
    }

    function captureVisionFrame() {
      if (!state.visionStream || !el.visionPreview.videoWidth || !el.visionPreview.videoHeight) {
        return null;
      }
      const canvas = document.createElement("canvas");
      const scale = Math.min(1, 1024 / Math.max(el.visionPreview.videoWidth, el.visionPreview.videoHeight));
      canvas.width = Math.max(1, Math.round(el.visionPreview.videoWidth * scale));
      canvas.height = Math.max(1, Math.round(el.visionPreview.videoHeight * scale));
      const ctx = canvas.getContext("2d");
      ctx.drawImage(el.visionPreview, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", 0.82);
    }

    function startVoice() {
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!Recognition) {
        addMessage("system", "Voice input is not supported in this browser.");
        return;
      }
      const recognition = new Recognition();
      recognition.lang = "en-IN";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => {
        el.voiceBtn.textContent = "ON";
        el.statusTitle.textContent = "Listening";
        el.statusCopy.textContent = "Speak your command.";
      };
      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        el.prompt.value = transcript;
        el.prompt.focus();
        if (state.visionMode !== "none") {
          sendVisionPrompt(transcript);
        } else {
          sendPrompt(transcript);
        }
      };
      recognition.onerror = () => addMessage("system", "Voice input stopped before a command was captured.");
      recognition.onend = () => {
        el.voiceBtn.textContent = "MIC";
        if (!state.busy) setBusy(false);
      };
      recognition.start();
    }

    el.composer.addEventListener("submit", (event) => {
      event.preventDefault();
      sendPrompt(el.prompt.value);
    });

    document.getElementById("clearBtn").addEventListener("click", () => {
      el.prompt.value = "";
      el.prompt.focus();
    });

    document.getElementById("refreshBtn").addEventListener("click", loadState);
    el.voiceBtn.addEventListener("click", startVoice);
    el.visionAskBtn.addEventListener("click", () => sendVisionPrompt(el.prompt.value));
    el.coworkBtn.addEventListener("click", () => setCoworkMode(!state.coworkEnabled));
    document.getElementById("cameraBtn").addEventListener("click", () => startVision("camera"));
    document.getElementById("screenBtn").addEventListener("click", () => startVision("screen"));
    document.getElementById("stopVisionBtn").addEventListener("click", stopVision);
    el.speakBtn.addEventListener("click", () => {
      state.speaking = !state.speaking;
      el.speakBtn.textContent = state.speaking ? "MUTE" : "VOL";
    });

    document.querySelectorAll(".quick button").forEach((button) => {
      button.addEventListener("click", () => {
        el.prompt.value = button.dataset.prompt;
        el.prompt.focus();
      });
    });

    document.querySelectorAll(".tabs button").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tabs button").forEach((tab) => tab.classList.remove("active"));
        button.classList.add("active");
        state.tab = button.dataset.tab;
        renderState();
      });
    });

    el.prompt.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendPrompt(el.prompt.value);
      }
    });

    function animateCore() {
      const canvas = document.getElementById("core");
      const ctx = canvas.getContext("2d");
      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;
      let frame = 0;
      let particles = [];
      let mouse = { x: -100, y: -100 };

      canvas.addEventListener("mousemove", (e) => {
        const rect = canvas.getBoundingClientRect();
        const scaleX = w / rect.width;
        const scaleY = h / rect.height;
        mouse.x = (e.clientX - rect.left) * scaleX;
        mouse.y = (e.clientY - rect.top) * scaleY;
        
        for (let i = 0; i < 2; i++) {
          particles.push({
            x: mouse.x,
            y: mouse.y,
            vx: (Math.random() - 0.5) * 3,
            vy: (Math.random() - 0.5) * 3,
            life: 1,
            size: Math.random() * 3 + 1
          });
        }
      });
      canvas.addEventListener("mouseleave", () => {
        mouse.x = -100;
        mouse.y = -100;
      });

      function drawRing(radius, rotation, color, segments) {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(rotation);
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        for (let i = 0; i < segments; i++) {
          const start = (Math.PI * 2 / segments) * i;
          const end = start + Math.PI / segments;
          ctx.beginPath();
          ctx.arc(0, 0, radius, start, end);
          ctx.stroke();
        }
        ctx.restore();
      }

      function draw() {
        frame += 0.012;
        ctx.clearRect(0, 0, w, h);
        ctx.globalCompositeOperation = "lighter";

        const glow = ctx.createRadialGradient(cx, cy, 20, cx, cy, 210);
        glow.addColorStop(0, "rgba(92, 221, 255, 0.32)");
        glow.addColorStop(0.55, "rgba(92, 221, 255, 0.08)");
        glow.addColorStop(1, "rgba(92, 221, 255, 0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(cx, cy, 220, 0, Math.PI * 2);
        ctx.fill();

        drawRing(210, frame, "rgba(92, 221, 255, 0.52)", 32);
        drawRing(178, -frame * 1.4, "rgba(111, 255, 195, 0.42)", 22);
        drawRing(146, frame * 1.9, "rgba(255, 209, 102, 0.36)", 18);
        drawRing(104, -frame * 2.3, "rgba(92, 221, 255, 0.7)", 14);

        ctx.strokeStyle = "rgba(92, 221, 255, 0.2)";
        ctx.lineWidth = 1;
        for (let i = 0; i < 10; i++) {
          const angle = frame * 0.6 + i * Math.PI * 0.2;
          ctx.beginPath();
          ctx.moveTo(cx + Math.cos(angle) * 130, cy + Math.sin(angle) * 130);
          ctx.lineTo(cx + Math.cos(angle) * 230, cy + Math.sin(angle) * 230);
          ctx.stroke();
        }

        for (let i = 0; i < particles.length; i++) {
          let p = particles[i];
          p.x += p.vx;
          p.y += p.vy;
          p.life -= 0.02;
          if (p.life <= 0) {
            particles.splice(i, 1);
            i--;
            continue;
          }
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(92, 221, 255, ${p.life * 0.6})`;
          ctx.fill();
        }

        requestAnimationFrame(draw);
      }

      draw();
    }

    addMessage("assistant", "MOSES interface online. What shall we handle first?");
    loadState();
    animateCore();
  </script>
</body>
</html>
"""


def parse_data_url_image(data_url: str) -> tuple[str, bytes]:
    if "," not in data_url:
        raise ValueError("Image must be a data URL.")

    header, encoded = data_url.split(",", 1)
    if not header.startswith("data:image/") or ";base64" not in header:
        raise ValueError("Only base64 image data URLs are supported.")

    mime_type = header.removeprefix("data:").split(";", 1)[0]
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Only JPEG, PNG, and WebP images are supported.")

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ValueError("Image data is not valid base64.") from exc

    if len(image_bytes) > 8 * 1024 * 1024:
        raise ValueError("Image is too large.")
    return mime_type, image_bytes


class GuiState:
    def __init__(self, store: AssistantStore, model: str, system_instruction: str, workspace: WorkspaceAccess) -> None:
        self.store = store
        self.model = model
        self.system_instruction = system_instruction
        self.workspace = workspace
        self.agent: MosesAgent | None = None
        self.agent_error: str | None = None
        self.lock = threading.Lock()
        self._load_agent()

    def _load_agent(self) -> None:
        try:
            self.agent = MosesAgent(self.store, self.model, self.system_instruction, workspace=self.workspace)
            self.agent_error = None
        except Exception as exc:
            self.agent = None
            self.agent_error = str(exc)

    def ask(self, message: str, backend: str = "gemini") -> str:
        with self.lock:
            if self.agent is None:
                self._load_agent()
            if self.agent is None:
                raise RuntimeError(self.agent_error or "MOSES is not configured.")
            return self.agent.ask(message, backend=backend)

    def ask_vision(self, message: str, image_data_url: str, backend: str = "gemini") -> str:
        with self.lock:
            if self.agent is None:
                self._load_agent()
            if self.agent is None:
                raise RuntimeError(self.agent_error or "MOSES is not configured.")
            mime_type, image_bytes = parse_data_url_image(image_data_url)
            return self.agent.ask_with_image(message, image_bytes, mime_type, backend=backend)

    def set_cowork_mode(self, enabled: bool) -> dict[str, Any]:
        with self.lock:
            self.workspace.cowork_enabled = enabled
            return {"cowork_enabled": self.workspace.cowork_enabled}

    def update_cowork_change(self, change_id: str, action: str) -> dict[str, Any]:
        with self.lock:
            if action == "apply":
                return self.workspace.apply_change(change_id)
            if action == "reject":
                return self.workspace.reject_change(change_id)
            return {"id": change_id, "error": "Action must be apply or reject."}

    def snapshot(self) -> dict[str, Any]:
        state = self.store._read()
        state["model"] = self.model
        state["workspace"] = str(self.workspace.root)
        state["cowork_enabled"] = self.workspace.cowork_enabled
        state["pending_changes"] = self.workspace.list_pending_changes()
        state["agent_ready"] = self.agent is not None
        state["agent_error"] = self.agent_error
        return state


class MosesGuiHandler(BaseHTTPRequestHandler):
    gui_state: GuiState

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send_html(HTML)
            return
        if self.path == "/api/state":
            self._send_json(self.gui_state.snapshot())
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            if self.path == "/api/vision":
                self._handle_vision()
                return
            if self.path == "/api/cowork":
                self._handle_cowork()
                return
            if self.path == "/api/cowork-change":
                self._handle_cowork_change()
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            payload = self._read_json()
            message = str(payload.get("message", "")).strip()
            backend = str(payload.get("backend", "gemini")).strip()
            if not message:
                self._send_json({"error": "Message is required."}, HTTPStatus.BAD_REQUEST)
                return
            reply = self.gui_state.ask(message, backend)
            self._send_json({"reply": reply})
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)

    def _handle_cowork(self) -> None:
        try:
            payload = self._read_json()
            enabled = bool(payload.get("enabled", False))
            self._send_json(self.gui_state.set_cowork_mode(enabled))
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)

    def _handle_cowork_change(self) -> None:
        try:
            payload = self._read_json()
            change_id = str(payload.get("id", "")).strip()
            action = str(payload.get("action", "")).strip().lower()
            if not change_id:
                self._send_json({"error": "Change id is required."}, HTTPStatus.BAD_REQUEST)
                return
            result = self.gui_state.update_cowork_change(change_id, action)
            status = HTTPStatus.BAD_REQUEST if result.get("error") else HTTPStatus.OK
            self._send_json(result, status)
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)

    def _handle_vision(self) -> None:
        try:
            payload = self._read_json()
            message = str(payload.get("message", "")).strip() or "What do you see right now?"
            image = str(payload.get("image", "")).strip()
            backend = str(payload.get("backend", "gemini")).strip()
            if not image:
                self._send_json({"error": "Image is required."}, HTTPStatus.BAD_REQUEST)
                return
            reply = self.gui_state.ask_vision(message, image, backend)
            self._send_json({"reply": reply})
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MOSES Jarvis-style browser GUI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument("--model", default=os.getenv("MOSES_MODEL", DEFAULT_MODEL), help="Gemini model name.")
    parser.add_argument("--timezone", default=os.getenv("MOSES_TIMEZONE", DEFAULT_TIMEZONE), help="IANA timezone.")
    parser.add_argument(
        "--data-file",
        default=os.getenv("MOSES_DATA_FILE", str(Path("data") / "moses_state.json")),
        help="Path to the local JSON memory store.",
    )
    parser.add_argument(
        "--workspace",
        default=os.getenv("MOSES_WORKSPACE", str(Path.cwd())),
        help="Directory MOSES can read and edit with workspace tools.",
    )
    return parser


def print_setup_error(error: Exception) -> None:
    print(f"MOSES GUI setup error: {error}")
    print()
    print("Quick setup:")
    print("  1. python -m pip install -r requirements.txt")
    print("  2. Create .env with: GEMINI_API_KEY=your_api_key_here")
    print("  3. (Optional) Add NOTION_API_KEY=your_notion_secret to use Notion tools")
    print("  4. Run: python moses_gui.py")


def main() -> int:
    if load_dotenv is None:
        print_setup_error(RuntimeError("python-dotenv is not installed."))
        return 1

    load_dotenv()
    args = build_parser().parse_args()
    store = AssistantStore(Path(args.data_file), timezone=args.timezone)
    gui_state = GuiState(store, args.model, SYSTEM_INSTRUCTION, WorkspaceAccess(Path(args.workspace)))

    MosesGuiHandler.gui_state = gui_state
    server = ThreadingHTTPServer((args.host, args.port), MosesGuiHandler)
    url = f"http://{args.host}:{args.port}"

    print(f"MOSES GUI running at {url}")
    if gui_state.agent_error:
        print(f"Setup notice: {gui_state.agent_error}")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMOSES GUI stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
