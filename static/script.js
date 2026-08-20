const API_BASE_URL = "https://tee-time-api.onrender.com"; // Your Render API URL

document.addEventListener("DOMContentLoaded", () => {
    const searchRowsContainer = document.getElementById("searchRows");
    const addRowButton = document.getElementById("addRowButton");
    const teeTimeForm = document.getElementById("teeTimeForm");
    const messageDiv = document.getElementById("message");
    const currentConfigP = document.getElementById("currentConfig");

    // Elements for pause/resume functionality
    const togglePauseButton = document.getElementById("togglePauseButton");
    const scraperStatusP = document.getElementById("scraperStatus");

    let rowCount = 0;

    // Helper to convert MM/DD/YYYY to YYYY-MM-DD for date input value
    function convertDateToInputFormat(dateStr) {
        if (!dateStr) return '';
        const parts = dateStr.split('/');
        if (parts.length === 3) {
            return `${parts[2]}-${parts[0].padStart(2, '0')}-${parts[1].padStart(2, '0')}`;
        }
        return '';
    }

    // Helper to convert YYYY-MM-DD from date input value to MM/DD/YYYY for API
    function convertDateToApiFormat(dateStr) {
        if (!dateStr) return '';
        const parts = dateStr.split('-');
        if (parts.length === 3) {
            return `${parts[1]}/${parts[2]}/${parts[0]}`;
        }
        return '';
    }

    // Helper to convert HH:MM AM/PM to HH:MM (24-hour) for time input value
    function convertTimeToInputFormat(timeStr) {
        if (!timeStr) return '';
        const [time, period] = timeStr.split(' ');
        let [hours, minutes] = time.split(':');
        if (period === 'PM' && hours !== '12') {
            hours = parseInt(hours, 10) + 12;
        } else if (period === 'AM' && hours === '12') {
            hours = '00';
        }
        return `${hours.toString().padStart(2, '0')}:${minutes}`;
    }

    // Helper to convert HH:MM (24-hour) from time input value to HH:MM AM/PM for API
    function convertTimeToApiFormat(timeStr) {
        if (!timeStr) return '';
        const [hours, minutes] = timeStr.split(':');
        let h = parseInt(hours, 10);
        const period = h >= 12 ? 'PM' : 'AM';
        h = h % 12;
        h = h === 0 ? 12 : h; // The hour '0' should be '12 AM'
        return `${h.toString().padStart(2, '0')}:${minutes} ${period}`;
    }

    // Build a single search row (date/start/end/course + remove button)
    function addSearchRow(entry) {
        entry = entry || {};
        rowCount += 1;
        const rowId = `row-${rowCount}`;

        const row = document.createElement("div");
        row.className = "search-row";
        row.dataset.rowId = rowId;

        row.innerHTML = `
            <div class="row-title">Search ${rowCount}</div>
            <div class="input-group">
                <label>Date:</label>
                <input type="date" class="row-date" required>
            </div>
            <div class="input-group">
                <label>Start Time:</label>
                <input type="time" class="row-start" required>
            </div>
            <div class="input-group">
                <label>End Time:</label>
                <input type="time" class="row-end" required>
            </div>
            <div class="input-group">
                <label>Course:</label>
                <select class="row-course" required>
                    <option value="All">All</option>
                    <option value="Highlands">Highlands</option>
                    <option value="Fairways">Fairways</option>
                    <option value="Meadows">Meadows</option>
                </select>
            </div>
            <button type="button" class="remove-row-button">Remove</button>
        `;

        row.querySelector(".row-date").value = convertDateToInputFormat(entry.date);
        row.querySelector(".row-start").value = convertTimeToInputFormat(entry.start);
        row.querySelector(".row-end").value = convertTimeToInputFormat(entry.end);
        row.querySelector(".row-course").value = entry.course || "All";

        row.querySelector(".remove-row-button").addEventListener("click", () => {
            // Always keep at least one row
            if (searchRowsContainer.children.length > 1) {
                row.remove();
                renumberRows();
            } else {
                showMessage("At least one search is required.", "error");
            }
        });

        searchRowsContainer.appendChild(row);
    }

    function renumberRows() {
        const rows = searchRowsContainer.querySelectorAll(".search-row");
        rows.forEach((row, index) => {
            row.querySelector(".row-title").textContent = `Search ${index + 1}`;
        });
    }

    function renderSearchRows(searches) {
        searchRowsContainer.innerHTML = "";
        rowCount = 0;
        if (!searches || searches.length === 0) {
            addSearchRow();
        } else {
            searches.forEach(entry => addSearchRow(entry));
        }
    }

    addRowButton.addEventListener("click", () => addSearchRow());

    // Function to fetch and display current config (updated to include pause status)
    async function fetchCurrentConfig() {
        try {
            const response = await fetch(`${API_BASE_URL}/get`);
            const data = await response.json();
            if (response.ok) {
                const config = data.current_config;
                const searches = config.searches || [];

                currentConfigP.textContent = searches.map((s, i) =>
                    `Search ${i + 1} - Date: ${s.date}, Start: ${s.start}, End: ${s.end}, Course: ${s.course || 'All'}`
                ).join('\n');

                renderSearchRows(searches);

                // Update pause/resume button and status
                updatePauseStatus(config.is_paused);
            } else {
                currentConfigP.textContent = `Error fetching config: ${data.error || 'Unknown error'}`;
                renderSearchRows();
                // Handle error for pause status as well
                updatePauseStatus(false, true); // Assume not paused, show error
            }
        } catch (error) {
            currentConfigP.textContent = `Network error fetching config: ${error.message}`;
            console.error("Error fetching current config:", error);
            renderSearchRows();
            // Handle network error for pause status
            updatePauseStatus(false, true); // Assume not paused, show error
        }
    }

    // Helper to update the pause/resume button and status text
    function updatePauseStatus(isPaused, isError = false) {
        if (isError) {
            togglePauseButton.textContent = "Error loading status";
            scraperStatusP.textContent = "Could not load scraper status.";
            togglePauseButton.disabled = true; // Disable button on error
            return;
        }

        if (isPaused) {
            togglePauseButton.textContent = "Resume Scraper";
            togglePauseButton.classList.remove("bg-green-600"); // Example Tailwind class removal
            togglePauseButton.classList.add("bg-red-600"); // Example Tailwind class add
            scraperStatusP.textContent = "Scraper is PAUSED.";
            scraperStatusP.style.color = "#dc3545"; // Red
        } else {
            togglePauseButton.textContent = "Pause Scraper";
            togglePauseButton.classList.remove("bg-red-600"); // Example Tailwind class removal
            togglePauseButton.classList.add("bg-green-600"); // Example Tailwind class add
            scraperStatusP.textContent = "Scraper is RUNNING.";
            scraperStatusP.style.color = "#28a745"; // Green
        }
        togglePauseButton.disabled = false; // Enable button once status is known
    }

    // Function to handle form submission
    teeTimeForm.addEventListener("submit", async (event) => {
        event.preventDefault(); // Stop the page from reloading

        const rows = searchRowsContainer.querySelectorAll(".search-row");
        const searches = [];

        for (const row of rows) {
            const date = row.querySelector(".row-date").value; // YYYY-MM-DD
            const start = row.querySelector(".row-start").value; // HH:MM (24-hour)
            const end = row.querySelector(".row-end").value; // HH:MM (24-hour)
            const course = row.querySelector(".row-course").value;

            if (!date || !start || !end || !course) {
                showMessage("Please fill in all fields for every search.", "error");
                return;
            }

            searches.push({
                date: convertDateToApiFormat(date),
                start: convertTimeToApiFormat(start),
                end: convertTimeToApiFormat(end),
                course: course
            });
        }

        try {
            showMessage("Updating config...", ""); // Clear previous message
            const response = await fetch(`${API_BASE_URL}/set`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ searches })
            });
            const data = await response.json();

            if (response.ok && !data.error) {
                showMessage(data.message || "Config updated successfully!", "success");
                fetchCurrentConfig(); // Refresh current config display
            } else {
                showMessage(data.error || "Failed to update config.", "error");
            }
        } catch (error) {
            showMessage(`Network error: ${error.message}`, "error");
            console.error("Error updating config:", error);
        }
    });

    // Event listener for the toggle pause button
    togglePauseButton.addEventListener("click", async () => {
        try {
            showMessage("Toggling scraper status...", "");
            const response = await fetch(`${API_BASE_URL}/toggle-scraper-pause`);
            const data = await response.json();

            if (response.ok) {
                showMessage(data.message || "Scraper status toggled! ", "success");
                updatePauseStatus(data.is_paused); // Update UI based on new state
            } else {
                showMessage(data.error || "Failed to toggle scraper status.", "error");
            }
        } catch (error) {
            showMessage(`Network error toggling scraper: ${error.message}`, "error");
            console.error("Error toggling scraper status:", error);
        }
    });

    // Helper to display messages
    function showMessage(msg, type) {
        messageDiv.textContent = msg;
        messageDiv.className = `message ${type}`; // Add class for styling (success/error)
        setTimeout(() => {
            messageDiv.textContent = '';
            messageDiv.className = 'message';
        }, 5000); // Clear message after 5 seconds
    }

    // Fetch config on page load
    fetchCurrentConfig();
});
