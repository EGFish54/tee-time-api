const API_BASE_URL = "https://tee-time-api.onrender.com"; // Your Render API URL

document.addEventListener("DOMContentLoaded", () => {
    const dateInput = document.getElementById("date");
    const startTimeInput = document.getElementById("start");
    const endTimeInput = document.getElementById("end");
    const updateButton = document.getElementById("updateButton");
    const messageDiv = document.getElementById("message");
    const currentConfigP = document.getElementById("currentConfig");

    // NEW: Elements for pause/resume functionality
    const togglePauseButton = document.getElementById("togglePauseButton");
    const scraperStatusP = document.getElementById("scraperStatus");
    // END NEW

    // Function to fetch and display current config (updated to include pause status)
    async function fetchCurrentConfig() {
        try {
            const response = await fetch(`${API_BASE_URL}/get`);
            const data = await response.json();
            if (response.ok) {
                const config = data.current_config;
                currentConfigP.textContent = `Date: ${config.date}\nStart: ${config.start}\nEnd: ${config.end}`;
                // Pre-fill input fields with current values
                dateInput.value = config.date;
                startTimeInput.value = config.start;
                endTimeInput.value = config.end;

                // NEW: Update pause/resume button and status
                updatePauseStatus(config.is_paused);
                // END NEW
            } else {
                currentConfigP.textContent = `Error fetching config: ${data.error || 'Unknown error'}`;
                // NEW: Handle error for pause status as well
                updatePauseStatus(false, true); // Assume not paused, show error
                // END NEW
            }
        } catch (error) {
            currentConfigP.textContent = `Network error fetching config: ${error.message}`;
            console.error("Error fetching current config:", error);
            // NEW: Handle network error for pause status
            updatePauseStatus(false, true); // Assume not paused, show error
            // END NEW
        }
    }

    // NEW: Helper to update the pause/resume button and status text
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
    // END NEW

    // Function to handle update button click
    updateButton.addEventListener("click", async (event) => {
        event.preventDefault(); // Stop the page from reloading

        const date = dateInput.value;
        const start = startTimeInput.value;
        const end = endTimeInput.value;

        if (!date || !start || !end) {
            showMessage("Please fill in all fields.", "error");
            return;
        }

        // Encode parameters for URL
        const encodedDate = encodeURIComponent(date);
        const encodedStart = encodeURIComponent(start);
        const encodedEnd = encodeURIComponent(end);

        try {
            const url = `${API_BASE_URL}/set?date=${encodedDate}&start=${encodedStart}&end=${encodedEnd}`;
            showMessage("Updating config...", ""); // Clear previous message
            const response = await fetch(url);
            const data = await response.json();

            if (response.ok) {
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

    // NEW: Event listener for the toggle pause button
    togglePauseButton.addEventListener("click", async () => {
        try {
            showMessage("Toggling scraper status...", "");
            const response = await fetch(`${API_BASE_URL}/toggle-scraper-pause`);
            const data = await response.json();

            if (response.ok) {
                showMessage(data.message || "Scraper status toggled!", "success");
                updatePauseStatus(data.is_paused); // Update UI based on new state
            } else {
                showMessage(data.error || "Failed to toggle scraper status.", "error");
            }
        } catch (error) {
            showMessage(`Network error toggling scraper: ${error.message}`, "error");
            console.error("Error toggling scraper status:", error);
        }
    });
    // END NEW

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
