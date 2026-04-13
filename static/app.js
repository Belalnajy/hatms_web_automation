document.addEventListener("DOMContentLoaded", () => {
    const cookieInput = document.getElementById("cookie-input");
    const startBtn = document.getElementById("start-btn");
    const btnText = startBtn.querySelector(".btn-text");
    const btnLoader = startBtn.querySelector(".btn-loader");
    const statusIndicator = document.getElementById("status-indicator");
    const terminalBody = document.getElementById("terminal-body");
    const historyList = document.getElementById("history-list");
    const historyEmpty = document.getElementById("history-empty");
    const clearHistoryBtn = document.getElementById("clear-history-btn");
    const historyToggle = document.getElementById("history-toggle");
    const historyContent = document.getElementById("history-content");
    const historyCount = document.getElementById("history-count");

    const STORAGE_KEY = "hatms_history";

    // ─── History Toggle ───
    historyToggle.addEventListener("click", () => {
        historyContent.classList.toggle("collapsed");
        historyToggle.classList.toggle("open");
    });

    // ─── Load History ───
    function loadHistory() {
        const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        renderHistory(data);
        return data;
    }

    function saveHistory(data) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        renderHistory(data);
    }

    function addHistoryEntry(name, session, status = "completed") {
        const data = loadHistory();
        data.unshift({
            name: name,
            session: session,
            status: status,
            timestamp: new Date().toISOString(),
        });
        saveHistory(data);
    }

    function removeHistoryEntry(index) {
        const data = loadHistory();
        data.splice(index, 1);
        saveHistory(data);
    }

    function renderHistory(data) {
        historyCount.textContent = data.length;

        if (data.length === 0) {
            historyEmpty.classList.remove("hidden");
            historyList.innerHTML = "";
            clearHistoryBtn.classList.add("hidden");
            return;
        }

        historyEmpty.classList.add("hidden");
        clearHistoryBtn.classList.remove("hidden");

        historyList.innerHTML = data.map((item, i) => {
            const date = new Date(item.timestamp);
            const formattedDate = date.toLocaleDateString("en-US", {
                month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
            });
            const statusIcon = item.status === "completed" ? "✅" : "❌";
            const statusClass = item.status === "completed" ? "history-success" : "history-fail";
            // Mask session: show first 6 + last 4
            const masked = item.session.length > 12
                ? item.session.slice(0, 6) + "••••" + item.session.slice(-4)
                : item.session;

            return `
                <div class="history-item ${statusClass}" data-index="${i}">
                    <div class="history-item-top">
                        <div class="history-name">
                            <span class="history-status-icon">${statusIcon}</span>
                            <span class="history-account-name">${escapeHtml(item.name)}</span>
                        </div>
                        <div class="history-date">${formattedDate}</div>
                    </div>
                    <div class="history-item-bottom">
                        <div class="history-session">
                            <span class="session-label">Session:</span>
                            <code class="session-value">${masked}</code>
                            <button class="history-action-btn copy-btn" title="Copy Session" data-session="${escapeHtml(item.session)}">
                                📋
                            </button>
                            <button class="history-action-btn reuse-btn" title="Reuse" data-session="${escapeHtml(item.session)}">
                                🔄
                            </button>
                        </div>
                        <button class="history-action-btn delete-btn" title="Delete" data-index="${i}">🗑️</button>
                    </div>
                </div>
            `;
        }).join("");

        // Event listeners
        historyList.querySelectorAll(".copy-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(btn.dataset.session).then(() => {
                    btn.textContent = "✅";
                    setTimeout(() => btn.textContent = "📋", 1500);
                });
            });
        });

        historyList.querySelectorAll(".reuse-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                cookieInput.value = btn.dataset.session;
                window.scrollTo({ top: 0, behavior: "smooth" });
                cookieInput.focus();
            });
        });

        historyList.querySelectorAll(".delete-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.dataset.index);
                const item = btn.closest(".history-item");
                item.style.animation = "slideOut 0.3s ease forwards";
                setTimeout(() => removeHistoryEntry(idx), 300);
            });
        });
    }

    // ─── Clear All ───
    clearHistoryBtn.addEventListener("click", () => {
        if (confirm("Clear all history?")) {
            localStorage.removeItem(STORAGE_KEY);
            loadHistory();
        }
    });

    // ─── Utility ───
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    // ─── Terminal Logging ───
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
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }

    // ─── Start Automation ───
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

        let finalStatus = "completed";
        let accountName = "Unknown";

        try {
            const response = await fetch("/api/index", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ cookie: cookie })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n\n');
                for (let line of lines) {
                    if (line.startsWith('data: ')) {
                        const logText = line.substring(6);
                        if (logText.trim().length > 0) {
                            addLog(logText);

                            // Parse account name from script output
                            const nameMatch = logText.match(/👤 ACCOUNT_NAME:\s*(.+)/);
                            if (nameMatch) {
                                accountName = nameMatch[1].trim();
                            }

                            // Detect failure
                            if (logText.includes("❌ Could not pass") || logText.includes("❌ Could not extract SESSKEY")) {
                                finalStatus = "failed";
                            }
                        }
                    }
                }
            }
            statusIndicator.innerHTML = `✅ Task completed.`;
        } catch (error) {
            addLog(`❌ An unexpected error occurred: ${error.message}`);
            statusIndicator.innerHTML = `❌ Connection failed.`;
            finalStatus = "failed";
        } finally {
            // Save to history with auto-extracted name
            const cleanSession = cookie.replace("MoodleSession=", "").trim();
            addHistoryEntry(accountName, cleanSession, finalStatus);

            // Restore UI
            startBtn.disabled = false;
            btnText.textContent = "Start Automation";
            btnLoader.classList.add("hidden");
            cookieInput.disabled = false;
            cookieInput.value = "";
        }
    });

    // ─── Initial Load ───
    loadHistory();
});
