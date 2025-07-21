const API_BASE_URL = "https://tee-time-api.onrender.com"; // Your Render API URL

document.addEventListener("DOMContentLoaded", () => {
    // --- FIX 1: Corrected Input IDs to match index.html ---
    const dateInput = document.getElementById("date"); // Changed from "dateInput"
    const startTimeInput = document.getElementById("start"); // Changed from "startTimeInput"
    const endTimeInput = document.getElementById("end"); // Changed from "endTimeInput"
    // --- End Fix 1 ---

    const updateButton = document.getElementById("updateButton");
    const messageDiv = document.getElementById("message");
    const currentConfigP = document.getElementById("currentConfig");

    // Function to fetch and display current config
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
            } else {
                currentConfigP.textContent = `Error fetching config: ${data.error || 'Unknown error'}`;
            }
        } catch (error) {
            currentConfigP.textContent = `Network error fetching config: ${error.message}`;
            console.error("Error fetching current config:", error);
        }
    }

    // Function to handle update button click
    updateButton.addEventListener("click", async (event) => { // Added 'event' parameter
        // --- FIX 2: Prevent default form submission ---
        event.preventDefault(); // Stop the page from reloading
        // --- End Fix 2 ---

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
            showMessage("Updating...", ""); // Clear previous message
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
