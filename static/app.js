document.addEventListener("DOMContentLoaded", () => {
    const cookieInput = document.getElementById("cookie-input");
    const startBtn = document.getElementById("start-btn");
    const btnText = startBtn.querySelector(".btn-text");
    const btnLoader = startBtn.querySelector(".btn-loader");
    const statusIndicator = document.getElementById("status-indicator");
    const terminalBody = document.getElementById("terminal-body");

    function addLog(message, type = "normal") {
        const div = document.createElement("div");
        div.className = `log-line`;
        if (message.includes("❌") || message.includes("Error") || message.includes("فشل")) {
            div.classList.add("log-error");
        } else if (message.includes("✅") || message.includes("PASSED") || message.includes("🎉")) {
            div.classList.add("log-success");
        }
        
        div.textContent = message;
        terminalBody.appendChild(div);
        
        // Auto scroll
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }

    startBtn.addEventListener("click", async () => {
        const cookie = cookieInput.value.trim();
        if (!cookie) {
            addLog("❌ Please enter your MoodleSession first.", "error");
            return;
        }

        // UI Loading state
        startBtn.disabled = true;
        btnText.textContent = "Processing...";
        btnLoader.classList.remove("hidden");
        cookieInput.disabled = true;
        statusIndicator.innerHTML = `<span class="pulsing">●</span> Executing now...`;
        
        // Clear terminal
        terminalBody.innerHTML = "";
        addLog("🚀 Initializing environment and connecting to server...");

        try {
            const response = await fetch("/api/index", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ cookie: cookie })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Stream response
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                // Chunk can contain multiple 'data: ...\n\n' blocks
                const lines = chunk.split('\n\n');
                for (let line of lines) {
                    if (line.startsWith('data: ')) {
                        const logText = line.substring(6); // remove 'data: '
                        if (logText.trim().length > 0) {
                            addLog(logText);
                        }
                    }
                }
            }
            statusIndicator.innerHTML = `✅ Task completed.`;
        } catch (error) {
            addLog(`❌ An unexpected error occurred: ${error.message}`);
            statusIndicator.innerHTML = `❌ Connection failed.`;
        } finally {
            // Restore UI
            startBtn.disabled = false;
            btnText.textContent = "Start Automation";
            btnLoader.classList.add("hidden");
            cookieInput.disabled = false;
        }
    });
});
