
(() => {
  const SERVER_URL = "http://localhost:3000";

  const socket = io(SERVER_URL, {
    autoConnect: true,
    reconnection: true
  });

  const nameInput = document.getElementById("player-name");
  const codeInput = document.getElementById("room-code");
  const hostButton = document.getElementById("host-game");
  const joinButton = document.getElementById("join-game");
  const leaveButton = document.getElementById("leave-game");
  const status = document.getElementById("multiplayer-status");
  const playerList = document.getElementById("player-list");

  let currentRoom = null;
  const remotePlayers = new Map();

  function setStatus(message) {
    status.textContent = message;
  }

  function getPlayerName() {
    return nameInput.value.trim() || "Player";
  }

  function enterRoom(result) {
    if (!result || !result.ok) {
      setStatus(result?.error || "Could not enter room.");
      return;
    }

    currentRoom = result.room.code;
    codeInput.value = currentRoom;
    leaveButton.hidden = false;

    setStatus(`Connected to room ${currentRoom}`);
    renderPlayers(result.room);
  }

  function renderPlayers(room) {
    if (!room) return;

    playerList.replaceChildren();

    for (const player of room.players) {
      const item = document.createElement("li");
      const role = player.id === room.hostId ? " (Host)" : "";

      item.textContent =
        `${player.name}${role}` +
        (player.id === socket.id ? " — You" : "");

      playerList.appendChild(item);
    }

    setStatus(
      `Room ${room.code} · ${room.players.length} player(s)`
    );
  }

  socket.on("connect", () => {
    setStatus("Connected to multiplayer server.");
  });

  socket.on("disconnect", () => {
    setStatus("Disconnected. Reconnecting...");
    currentRoom = null;
    remotePlayers.clear();
    playerList.replaceChildren();
    leaveButton.hidden = true;
  });

  socket.on("connect_error", () => {
    setStatus("Cannot connect. Is the server running on port 3000?");
  });

  socket.on("room:update", room => {
    if (room.code === currentRoom) {
      renderPlayers(room);
    }
  });

  socket.on("room:host-changed", () => {
    setStatus(`You are now hosting room ${currentRoom}.`);
  });

  socket.on("player:moved", data => {
    // Store remote positions for your game renderer to use.
    remotePlayers.set(data.id, {
      x: data.x,
      y: data.y,
      z: data.z
    });

    // Let your existing game code react to remote movement.
    window.dispatchEvent(
      new CustomEvent("snipernet:player-moved", {
        detail: data
      })
    );
  });

  hostButton.addEventListener("click", () => {
    if (!socket.connected) {
      setStatus("Waiting for server connection...");
      return;
    }

    socket.emit(
      "room:host",
      { name: getPlayerName() },
      enterRoom
    );
  });

  joinButton.addEventListener("click", () => {
    if (!socket.connected) {
      setStatus("Waiting for server connection...");
      return;
    }

    const code = codeInput.value.trim().toUpperCase();

    if (!code) {
      setStatus("Enter a room code first.");
      return;
    }

    socket.emit(
      "room:join",
      {
        code,
        name: getPlayerName()
      },
      enterRoom
    );
  });

  leaveButton.addEventListener("click", () => {
    socket.emit("room:leave");
    currentRoom = null;
    remotePlayers.clear();
    playerList.replaceChildren();
    leaveButton.hidden = true;
    setStatus("You left the room.");
  });

  // Public interface for connecting your existing game controls.
  window.SniperNetMultiplayer = {
    get roomCode() {
      return currentRoom;
    },

    get connected() {
      return socket.connected;
    },

    get remotePlayers() {
      return new Map(remotePlayers);
    },

    sendPosition(x, y, z = 0) {
      if (!currentRoom || !socket.connected) return;

      socket.emit("player:move", { x, y, z });
    },

    leave() {
      socket.emit("room:leave");
      currentRoom = null;
      remotePlayers.clear();
      playerList.replaceChildren();
      leaveButton.hidden = true;
      setStatus("You left the room.");
    }
  };
})();
