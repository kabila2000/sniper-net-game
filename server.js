
const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const crypto = require("crypto");

const app = express();
const server = http.createServer(app);

const io = new Server(server, {
  cors: {
    origin: process.env.CLIENT_ORIGIN || "http://localhost:8080"
  }
});

const rooms = new Map();

function makeRoomCode() {
  let code;
  do {
    code = crypto.randomBytes(3).toString("hex").toUpperCase();
  } while (rooms.has(code));
  return code;
}

function getPlayers(code) {
  const room = rooms.get(code);
  if (!room) return [];

  return [...room.players.entries()].map(([id, player]) => ({
    id,
    name: player.name
  }));
}

io.on("connection", (socket) => {
  socket.on("host", (name, callback) => {
    if (typeof callback !== "function") return;

    if (typeof name !== "string" || !name.trim()) {
      return callback({ error: "Enter your player name." });
    }

    const code = makeRoomCode();
    const room = {
      hostId: socket.id,
      players: new Map()
    };

    rooms.set(code, room);
    room.players.set(socket.id, {
      name: name.trim().slice(0, 20)
    });

    socket.join(code);
    socket.data.roomCode = code;

    callback({ roomCode: code, players: getPlayers(code) });
    io.to(code).emit("players", getPlayers(code));
  });

  socket.on("join", (data, callback) => {
    if (typeof callback !== "function") return;

    const code = String(data?.roomCode || "")
      .trim().toUpperCase();
    const name = String(data?.name || "").trim().slice(0, 20);
    const room = rooms.get(code);

    if (!room) return callback({ error: "Room not found." });
    if (!name) return callback({ error: "Enter your player name." });
    if (room.players.size >= 8) {
      return callback({ error: "Room is full." });
    }

    room.players.set(socket.id, { name });
    socket.join(code);
    socket.data.roomCode = code;

    callback({ roomCode: code, players: getPlayers(code) });
    io.to(code).emit("players", getPlayers(code));
  });

  socket.on("disconnect", () => {
    const code = socket.data.roomCode;
    const room = rooms.get(code);
    if (!room) return;

    room.players.delete(socket.id);

    if (room.players.size === 0) {
      rooms.delete(code);
      return;
    }

    if (room.hostId === socket.id) {
      room.hostId = room.players.keys().next().value;
      io.to(code).emit("hostChanged", { hostId: room.hostId });
    }

    io.to(code).emit("players", getPlayers(code));
  });
});

app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "Sniper Net Multiplayer" });
});

const PORT = process.env.PORT || 3000;

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Sniper Net server running on port ${PORT}`);
});
