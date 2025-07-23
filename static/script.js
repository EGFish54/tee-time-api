const API_BASE_URL = "https://tee-time-api.onrender.com"; // Your Render API URL

document.addEventListener("DOMContentLoaded", () => {
    const dateInput = document.getElementById("date");
    const startTimeInput = document.getElementById("start");
    const endTimeInput = document.getElementById("end");
    const updateButton = document.getElementById("updateButton");
    const messageDiv = document.getElementById("message");
    const currentConfigP = document.getElementById("currentConfig");

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

    // Function to fetch and display current config
    async function fetchCurrentConfig() {
        try {
            const response = await fetch(`${API_BASE_URL}/get`);
            const data = await response.json();
            if (response.ok) {
                const config = data.current_config;
                currentConfigP.textContent = `Date: ${config.date}\nStart: ${config.start}\nEnd: ${config.end}`;
                // Pre-fill input fields with current values, converting to input format
                dateInput.value = convertDateToInputFormat(config.date);
                startTimeInput.value = convertTimeToInputFormat(config.start);
                endTimeInput.value = convertTimeToInputFormat(config.end);
            } else {
                currentConfigP.textContent = `Error fetching config: ${data.error || 'Unknown error'}`;
            }
        } catch (error) {
            currentConfigP.textContent = `Network error fetching config: ${error.message}`;
            console.error("Error fetching current config:", error);
        }
    }

    // Function to handle update button click
    updateButton.addEventListener("click", async (event) => {
        event.preventDefault(); // Stop the page from reloading

        // Get values from input fields (these will be in the new formats)
        const date = dateInput.value; // YYYY-MM-DD
        const start = startTimeInput.value; // HH:MM (24-hour)
        const end = endTimeInput.value; // HH:MM (24-hour)

        if (!date || !start || !end) {
            showMessage("Please fill in all fields.", "error");
            return;
        }

        // Convert values to API expected format (MM/DD/YYYY and HH:MM AM/PM)
        const apiDate = convertDateToApiFormat(date);
        const apiStart = convertTimeToApiFormat(start);
        const apiEnd = convertTimeToApiFormat(end);

        // Encode parameters for URL
        const encodedDate = encodeURIComponent(apiDate);
        const encodedStart = encodeURIComponent(apiStart);
        const encodedEnd = encodeURIComponent(apiEnd);

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
