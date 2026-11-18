
const commandInput = document.getElementById("command");
const runButton = document.getElementById("run-command");
const output = document.getElementById("output");
const status = document.getElementById("status");

function runCommand() {
    const command = commandInput.value.trim();

    if (!command) return;

    if (command.toLowerCase() === "host") {
        output.textContent =
            "Host command received. Multiplayer connection is next.";
    } else if (command.toLowerCase().startsWith("join ")) {
        const roomCode = command.slice(5).trim();

        output.textContent = roomCode
            ? `Join command received for room ${roomCode}.`
            : "Usage: join ROOMCODE";
    } else {
        output.textContent = `Unknown command: ${command}`;
    }

    commandInput.value = "";
}

runButton.addEventListener("click", runCommand);

commandInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") runCommand();
});
