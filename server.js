
"use strict";

const express = require("express");
const http = require("http");
const crypto = require("crypto");
const { Server } = require("socket.io");

const app = express();
const server = http.createServer(app);

const io = new Server(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  },
  maxHttpBufferSize: 1e5
});

const PORT = Number(process.env.PORT) || 3000;
const MAX_PLAYERS = 8;
const MAX_CHAT_LENGTH = 250;
const rooms = new Map();

app.get("/health", (_req, res) => {
  res.json({
    status: "online",
    game: "Sniper Net Version 5",
    rooms: rooms.size,
    players: Array.from(rooms.values())
      .reduce((total, room) => total + room.players.size, 0)
  });
});

app.get("/rooms", (_req, res) => {
  res.json({
    rooms: Array.from(rooms.values()).map(room => ({
      code: room.code,
      players: room.players.size,
      maxPlayers: MAX_PLAYERS,
      status: room.status,
      map: room.map,
      mode: room.mode
    }))
  });
});

function cleanName(value) {
  return String(value || "Player")
    .replace(/[<>]/g, "")
    .trim()
    .slice(0, 20) || "Player";
}

function makeRoomCode() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

  let code;

  do {
    code = Array.from(
      crypto.randomBytes(6),
      byte => chars[byte % chars.length]
    ).join("");
  } while (rooms.has(code));

  return code;
}

function makePlayer(socket, name) {
  return {
    id: socket.id,
    name: cleanName(name),
    x: 0,
    y: 0,
    z: 0,
    team: "blue",
    ready: false,
    kills: 0,
    deaths: 0,
    health: 100,
    joinedAt: Date.now()
  };
}

function publicPlayer(player) {
  return {
    id: player.id,
    name: player.name,
    x: player.x,
    y: player.y,
    z: player.z,
    team: player.team,
    ready: player.ready,
    kills: player.kills,
    deaths: player.deaths,
    health: player.health
  };
}

function publicRoom(room) {
  return {
    code: room.code,
    hostId: room.hostId,
    players: Array.from(room.players.values()).map(publicPlayer),
    maxPlayers: MAX_PLAYERS,
    status: room.status,
    map: room.map,
    mode: room.mode,
    createdAt: room.createdAt
  };
}

function respond(callback, data) {
  if (typeof callback === "function") {
    callback(data);
  }
}

function roomFor(socket) {
  return rooms.get(socket.data.roomCode);
}

function publishRoom(room) {
  if (!room) return;

  const snapshot = publicRoom(room);

  io.to(room.code).emit("room:update", snapshot);

  // Backward-compatible event used by the original console.
  io.to(room.code).emit(
    "players",
    snapshot.players.map(player => ({
      ...player,
      isHost: player.id === room.hostId
    }))
  );
}

function leaveCurrentRoom(socket) {
  const code = socket.data.roomCode;
  if (!code) return;

  const room = rooms.get(code);
  socket.data.roomCode = null;

  socket.leave(code);

  if (!room) return;

  room.players.delete(socket.id);

  if (room.players.size === 0) {
    rooms.delete(code);
    return;
  }

  if (room.hostId === socket.id) {
    room.hostId = room.players.keys().next().value;
    io.to(room.hostId).emit("room:host-changed");
    io.to(room.hostId).emit("hostChanged");
  }

  if (room.status === "playing") {
    room.status = "playing";
  }

  publishRoom(room);
}

function createRoom(socket, name, callback) {
  leaveCurrentRoom(socket);

  const code = makeRoomCode();

  const room = {
    code,
    hostId: socket.id,
    players: new Map(),
    status: "lobby",
    map: "neon-rooftops",
    mode: "team-deathmatch",
    createdAt: Date.now()
  };

  room.players.set(socket.id, makePlayer(socket, name));
  rooms.set(code, room);

  socket.join(code);
  socket.data.roomCode = code;

  const snapshot = publicRoom(room);

  respond(callback, {
    ok: true,
    room: snapshot,
    roomCode: code,
    players: snapshot.players
  });

  publishRoom(room);
  console.log(`${cleanName(name)} hosted room ${code}`);
}

function joinRoom(socket, codeInput, name, callback) {
  const code = String(codeInput || "").trim().toUpperCase();
  const room = rooms.get(code);

  if (!room) {
    return respond(callback, {
      ok: false,
      error: "Room not found. Check the room code."
    });
  }

  if (room.players.size >= MAX_PLAYERS) {
    return respond(callback, {
      ok: false,
      error: `This room is full. Maximum: ${MAX_PLAYERS} players.`
    });
  }

  if (room.status === "playing") {
    return respond(callback, {
      ok: false,
      error: "This match has already started."
    });
  }

  leaveCurrentRoom(socket);

  const player = makePlayer(socket, name);

  // Balance teams by player count.
  const blueCount = Array.from(room.players.values())
    .filter(p => p.team === "blue").length;

  const redCount = Array.from(room.players.values())
    .filter(p => p.team === "red").length;

  player.team = blueCount <= redCount ? "blue" : "red";

  room.players.set(socket.id, player);

  socket.join(code);
  socket.data.roomCode = code;

  const snapshot = publicRoom(room);

  respond(callback, {
    ok: true,
    room: snapshot,
    roomCode: code,
    players: snapshot.players
  });

  publishRoom(room);
  console.log(`${player.name} joined room ${code}`);
}

io.on("connection", socket => {
  socket.data.roomCode = null;

  console.log("Connected:", socket.id);

  // New lobby interface.
  socket.on("room:host", (data = {}, callback) => {
    createRoom(socket, data.name, callback);
  });

  socket.on("room:join", (data = {}, callback) => {
    joinRoom(socket, data.code, data.name, callback);
  });

  // Original command-console compatibility.
  socket.on("host", (name, callback) => {
    createRoom(socket, name, callback);
  });

  socket.on("join", (data = {}, callback) => {
    joinRoom(
      socket,
      data.roomCode || data.code,
      data.name,
      callback
    );
  });

  socket.on("requestPlayers", (_data, callback) => {
    const room = roomFor(socket);

    if (!room) {
      return respond(callback, {
        error: "You are not in a room."
      });
    }

    const snapshot = publicRoom(room);

    respond(callback, {
      roomCode: room.code,
      players: snapshot.players
    });
  });

  socket.on("room:leave", (_data, callback) => {
  leaveCurrentRoom(socket);
  respond(callback, { ok: true });
});

  socket.on("leave", (_data, callback) => {
    leaveCurrentRoom(socket);
    respond(callback, { ok: true });
  });

  socket.on("disconnect", () => {
    leaveCurrentRoom(socket);
    console.log("Disconnected:", socket.id);
  });

  // Lobby readiness.
  socket.on("player:ready", (value, callback) => {
    const room = roomFor(socket);
    if (!room || room.status !== "lobby") {
      return respond(callback, {
        ok: false,
        error: "Ready status can only change in the lobby."
      });
    }

    const player = room.players.get(socket.id);
    if (!player) return;

    player.ready = Boolean(value);
    publishRoom(room);
    respond(callback, { ok: true });
  });

  // Team selection.
  socket.on("player:team", (team, callback) => {
    const room = roomFor(socket);
    if (!room || room.status !== "lobby") {
      return respond(callback, {
        ok: false,
        error: "Teams can only change in the lobby."
      });
    }

    if (!["blue", "red"].includes(team)) {
      return respond(callback, {
        ok: false,
        error: "Choose blue or red."
      });
    }

    room.players.get(socket.id).team = team;
    publishRoom(room);
    respond(callback, { ok: true });
  });

  // Chat: only room members can send messages.
  socket.on("chat:send", (value, callback) => {
    const room = roomFor(socket);
    const player = room?.players.get(socket.id);

    if (!room || !player) {
      return respond(callback, {
        ok: false,
        error: "Join a room before chatting."
      });
    }

    const text = String(value || "").trim().slice(0, MAX_CHAT_LENGTH);

    if (!text) {
      return respond(callback, {
        ok: false,
        error: "Message cannot be empty."
      });
    }

    const message = {
      id: crypto.randomUUID(),
      playerId: socket.id,
      name: player.name,
      text,
      time: Date.now()
    };

    io.to(room.code).emit("chat:message", message);
    respond(callback, { ok: true });
  });

  // Host starts a match after every player is ready.
  socket.on("match:start", (settings = {}, callback) => {
    const room = roomFor(socket);

    if (!room) {
      return respond(callback, {
        ok: false,
        error: "Join a room first."
      });
    }

    if (room.hostId !== socket.id) {
      return respond(callback, {
        ok: false,
        error: "Only the host can start the match."
      });
    }

    if (room.players.size < 2) {
      return respond(callback, {
        ok: false,
        error: "At least two players are required."
      });
    }

    const notReady = Array.from(room.players.values())
      .filter(player => player.id !== room.hostId && !player.ready);

    if (notReady.length > 0) {
      return respond(callback, {
        ok: false,
        error: "Wait for every other player to be ready."
      });
    }

    const allowedMaps = [
      "neon-rooftops",
      "canyon-run",
      "sky-tower",
      "the-pit",
      "molten-foundry",
      "glacier-base"
    ];

    const allowedModes = [
      "team-deathmatch",
      "free-for-all"
    ];

    if (allowedMaps.includes(settings.map)) {
      room.map = settings.map;
    }

    if (allowedModes.includes(settings.mode)) {
      room.mode = settings.mode;
    }

    room.status = "playing";

    io.to(room.code).emit("match:started", {
      code: room.code,
      map: room.map,
      mode: room.mode,
      startedAt: Date.now()
    });

    publishRoom(room);
    respond(callback, { ok: true, room: publicRoom(room) });
  });

  socket.on("match:end", callback => {
    const room = roomFor(socket);

    if (!room || room.hostId !== socket.id) {
      return respond(callback, {
        ok: false,
        error: "Only the host can end the match."
      });
    }

    room.status = "lobby";

    for (const player of room.players.values()) {
      player.ready = false;
      player.health = 100;
      player.x = 0;
      player.y = 0;
      player.z = 0;
    }

    io.to(room.code).emit("match:ended");
    publishRoom(room);
    respond(callback, { ok: true });
  });

  // Position updates are accepted only from a room member.
  socket.on("player:move", (data = {}) => {
    const room = roomFor(socket);
    const player = room?.players.get(socket.id);

    if (!room || !player || room.status !== "playing") return;

    for (const key of ["x", "y", "z"]) {
      if (typeof data[key] === "number" && Number.isFinite(data[key])) {
        player[key] = Math.max(-10000, Math.min(10000, data[key]));
      }
    }

    socket.to(room.code).emit("player:moved", {
      id: player.id,
      x: player.x,
      y: player.y,
      z: player.z
    });
  });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Sniper Net multiplayer: http://localhost:${PORT}`);
  console.log(`Maximum players per room: ${MAX_PLAYERS}`);
  console.log("Server ready.");
});
