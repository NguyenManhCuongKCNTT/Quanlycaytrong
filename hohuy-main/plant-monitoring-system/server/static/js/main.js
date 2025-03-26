let socket;
let temperatureChart;
let humidityChart;
let soilMoistureChart;
let lightLevelChart;
let currentMode = 'AUTO';
let currentPeriod = 'day';
let isUpdatingMode = false;
let thresholds = {
    temperature_min: 18.0,
    temperature_max: 30.0,
    soil_moisture_min: 30,
    humidity_min: 40.0,
    light_level_min: 30
};

document.addEventListener('DOMContentLoaded', function() {
    connectWebSocket();
    initCharts();
    loadHistoricalData('day');
    fetchThresholds();
    setupEventListeners();
});

function connectWebSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Đã kết nối với máy chủ WebSocket');
    });
    
    socket.on('disconnect', function() {
        console.log('Đã ngắt kết nối với máy chủ WebSocket');
    });
    
    socket.on('initial_state', function(data) {
        console.log('Nhận trạng thái ban đầu:', data);
        
        updateSensorValues(data.current_state);
        updateControlStatus(data.current_state);
        
        if (data.thresholds) {
            thresholds = data.thresholds;
            updateThresholdInputs();
        }
        
        currentMode = data.current_state.mode || 'AUTO';
        updateModeToggle();
    });
    
    socket.on('sensor_data_update', function(data) {
        updateSensorValues(data);
    });
    
    socket.on('temperature_update', function(data) {
        updateValue('temperature', data.value);
    });
    
    socket.on('humidity_update', function(data) {
        updateValue('humidity', data.value);
    });
    
    socket.on('soil_moisture_update', function(data) {
        updateValue('soil-moisture', data.value);
    });
    
    socket.on('light_level_update', function(data) {
        updateValue('light-level', data.value);
    });
    
    socket.on('pump_status_update', function(data) {
        updatePumpStatus(data.status);
    });
    
    socket.on('light_status_update', function(data) {
        updateLightStatus(data.status);
    });
    
    socket.on('mode_update', function(data) {
        if (currentMode !== data.mode) {
            currentMode = data.mode;
            updateModeToggle();
        }
    });
    
    socket.on('thresholds_update', function(data) {
        thresholds = data;
        updateThresholdInputs();
    });
}

function updateSensorValues(data) {
    if (data.temperature !== undefined) {
        updateValue('temperature', data.temperature);
    }
    
    if (data.humidity !== undefined) {
        updateValue('humidity', data.humidity);
    }
    
    if (data.soil_moisture !== undefined) {
        updateValue('soil-moisture', data.soil_moisture);
    }
    
    if (data.light_level !== undefined) {
        updateValue('light-level', data.light_level);
    }
}

function updateValue(sensorType, value) {
    const element = document.getElementById(`${sensorType}-value`);
    if (element) {
        const formattedValue = Number.isInteger(value) ? value : value.toFixed(1);
        
        element.classList.add('value-change');
        element.textContent = formattedValue;
        
        updateCircularProgress(sensorType, value);
        
        setTimeout(() => {
            element.classList.remove('value-change');
        }, 1000);
    }
}

function updateCircularProgress(sensorType, value) {
    let progressElement;
    let percentage;
    
    switch(sensorType) {
        case 'temperature':
            progressElement = document.getElementById('temp-progress');
            percentage = Math.min(100, Math.max(0, ((value - 10) / 30) * 100));
            break;
        case 'humidity':
            progressElement = document.getElementById('humidity-progress');
            percentage = value;
            break;
        case 'soil-moisture':
            progressElement = document.getElementById('soil-progress');
            percentage = value;
            break;
        case 'light-level':
            progressElement = document.getElementById('light-progress');
            percentage = value;
            break;
        default:
            return;
    }
    
    if (progressElement) {
        const gradientColors = calculateGradientColors(sensorType, percentage);
        progressElement.style.background = `conic-gradient(${gradientColors})`;
    }
}

function calculateGradientColors(sensorType, percentage) {
    if (percentage <= 0) {
        return '#e9ecef 0deg, #e9ecef 360deg';
    }
    
    const stopPoint = (percentage / 100) * 360;
    
    let colorStops;
    
    switch(sensorType) {
        case 'temperature':
            colorStops = `#ff4d6d 0deg, #ff758f ${stopPoint * 0.25}deg, #ff9e9e ${stopPoint * 0.5}deg, #ffccd5 ${stopPoint * 0.75}deg, #ffccd5 ${stopPoint}deg, #e9ecef ${stopPoint}deg, #e9ecef 360deg`;
            break;
        case 'humidity':
            colorStops = `#0077b6 0deg, #00b4d8 ${stopPoint * 0.25}deg, #90e0ef ${stopPoint * 0.5}deg, #ade8f4 ${stopPoint * 0.75}deg, #ade8f4 ${stopPoint}deg, #e9ecef ${stopPoint}deg, #e9ecef 360deg`;
            break;
        case 'soil-moisture':
            colorStops = `#0a9396 0deg, #2a9d8f ${stopPoint * 0.25}deg, #8ac926 ${stopPoint * 0.5}deg, #e9d8a6 ${stopPoint * 0.75}deg, #e9d8a6 ${stopPoint}deg, #e9ecef ${stopPoint}deg, #e9ecef 360deg`;
            break;
        case 'light-level':
            colorStops = `#ffd166 0deg, #ffda6e ${stopPoint * 0.25}deg, #ffe382 ${stopPoint * 0.5}deg, #ffeeab ${stopPoint * 0.75}deg, #ffeeab ${stopPoint}deg, #e9ecef ${stopPoint}deg, #e9ecef 360deg`;
            break;
        default:
            colorStops = '#e9ecef 0deg, #e9ecef 360deg';
    }
    
    return colorStops;
}

function updateControlStatus(data) {
    if (data.pump_status !== undefined) {
        updatePumpStatus(data.pump_status);
    }
    
    if (data.light_status !== undefined) {
        updateLightStatus(data.light_status);
    }
    
    if (data.mode !== undefined) {
        currentMode = data.mode;
        updateModeToggle();
    }
}

function updatePumpStatus(status) {
    const pumpStatus = document.getElementById('pump-status');
    if (pumpStatus) {
        pumpStatus.textContent = status;
        pumpStatus.className = `badge ${status === 'ON' ? 'status-on' : 'status-off'}`;
    }
}

function updateLightStatus(status) {
    const lightStatus = document.getElementById('light-status');
    if (lightStatus) {
        lightStatus.textContent = status;
        lightStatus.className = `badge ${status === 'ON' ? 'status-on' : 'status-off'}`;
    }
}

function updateModeToggle() {
    const autoModeToggle = document.getElementById('auto-mode-toggle');
    const modeLabel = document.getElementById('mode-label');
    const manualControls = document.getElementById('manual-controls');
    const autoThresholds = document.getElementById('auto-thresholds');
    
    if (autoModeToggle && modeLabel && manualControls && autoThresholds) {
        const isAuto = currentMode === 'AUTO';
        
        isUpdatingMode = true;
        
        autoModeToggle.checked = isAuto;
        modeLabel.textContent = isAuto ? 'Chế độ tự động' : 'Chế độ thủ công';
        
        if (isAuto) {
            manualControls.classList.add('d-none');
            autoThresholds.classList.remove('d-none');
        } else {
            manualControls.classList.remove('d-none');
            autoThresholds.classList.add('d-none');
        }
        
        setTimeout(() => {
            isUpdatingMode = false;
        }, 100);
    }
}

function updateThresholdInputs() {
    document.getElementById('temp-min').value = thresholds.temperature_min;
    document.getElementById('temp-max').value = thresholds.temperature_max;
    document.getElementById('soil-min').value = thresholds.soil_moisture_min;
    document.getElementById('humidity-min').value = thresholds.humidity_min;
    document.getElementById('light-min').value = thresholds.light_level_min;
}

function fetchThresholds() {
    fetch('/api/thresholds')
        .then(response => response.json())
        .then(data => {
            thresholds = data;
            updateThresholdInputs();
        })
        .catch(error => console.error('Lỗi khi lấy ngưỡng:', error));
}

function setupEventListeners() {
    const autoModeToggle = document.getElementById('auto-mode-toggle');
    autoModeToggle.addEventListener('change', function() {
        if (isUpdatingMode) {
            return;
        }
        
        const mode = this.checked ? 'AUTO' : 'MANUAL';
        socket.emit('set_mode', { mode: mode });
    });
    
    document.getElementById('pump-on-btn').addEventListener('click', function() {
        socket.emit('send_command', { command: 'PUMP_ON' });
    });
    
    document.getElementById('pump-off-btn').addEventListener('click', function() {
        socket.emit('send_command', { command: 'PUMP_OFF' });
    });
    
    document.getElementById('light-on-btn').addEventListener('click', function() {
        socket.emit('send_command', { command: 'LIGHT_ON' });
    });
    
    document.getElementById('light-off-btn').addEventListener('click', function() {
        socket.emit('send_command', { command: 'LIGHT_OFF' });
    });
    
    document.getElementById('threshold-form').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const newThresholds = {
            temperature_min: parseFloat(document.getElementById('temp-min').value),
            temperature_max: parseFloat(document.getElementById('temp-max').value),
            soil_moisture_min: parseInt(document.getElementById('soil-min').value),
            humidity_min: parseFloat(document.getElementById('humidity-min').value),
            light_level_min: parseInt(document.getElementById('light-min').value)
        };
        
        if (newThresholds.temperature_min >= newThresholds.temperature_max) {
            alert('Nhiệt độ tối thiểu phải nhỏ hơn nhiệt độ tối đa!');
            return;
        }
        
        if (newThresholds.soil_moisture_min < 0 || newThresholds.soil_moisture_min > 100) {
            alert('Độ ẩm đất phải nằm trong khoảng từ 0 đến 100!');
            return;
        }
        
        if (newThresholds.humidity_min < 0 || newThresholds.humidity_min > 100) {
            alert('Độ ẩm không khí phải nằm trong khoảng từ 0 đến 100!');
            return;
        }
        
        if (newThresholds.light_level_min < 0 || newThresholds.light_level_min > 100) {
            alert('Ánh sáng phải nằm trong khoảng từ 0 đến 100!');
            return;
        }
        
        socket.emit('set_thresholds', newThresholds);
    });
    
    const periodButtons = document.querySelectorAll('.period-btn');
    periodButtons.forEach(button => {
        button.addEventListener('click', function() {
            periodButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            const period = this.dataset.period;
            currentPeriod = period;
            loadHistoricalData(period);
        });
    });
}

function loadHistoricalData(period) {
    fetch(`/api/history?period=${period}&type=all`)
        .then(response => response.json())
        .then(data => {
            updateCharts(data.data, period);
        })
        .catch(error => console.error('Lỗi khi lấy dữ liệu lịch sử:', error));
}

function updateCharts(data, period) {
    if (!data || data.length === 0) {
        console.warn('Không có dữ liệu lịch sử');
        return;
    }
    
    const labels = data.map(item => {
        if (period === 'day') {
            return new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else if (period === 'week' || period === 'month') {
            return new Date(item.date).toLocaleDateString([], { month: 'short', day: 'numeric' });
        } else if (period === 'year') {
            return item.month;
        }
    });
    
    updateChart(temperatureChart, labels, data.map(item => item.temperature));
    updateChart(humidityChart, labels, data.map(item => item.humidity));
    updateChart(soilMoistureChart, labels, data.map(item => item.soil_moisture));
    updateChart(lightLevelChart, labels, data.map(item => item.light_level));
}

function updateChart(chart, labels, data) {
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.update();
}

function initCharts() {
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
            },
            tooltip: {
                mode: 'index',
                intersect: false,
            }
        },
        scales: {
            x: {
                ticks: {
                    maxRotation: 45,
                    minRotation: 45
                }
            }
        }
    };
    
    const tempCtx = document.getElementById('temperature-chart').getContext('2d');
    temperatureChart = new Chart(tempCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Nhiệt độ (°C)',
                data: [],
                borderColor: 'rgba(255, 99, 132, 1)',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                borderWidth: 2,
                tension: 0.1,
                fill: true,
            }]
        },
        options: {
            ...chartOptions,
            scales: {
                ...chartOptions.scales,
                y: {
                    title: {
                        display: true,
                        text: 'Nhiệt độ (°C)'
                    }
                }
            }
        }
    });
    
    const humidityCtx = document.getElementById('humidity-chart').getContext('2d');
    humidityChart = new Chart(humidityCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Độ ẩm không khí (%)',
                data: [],
                borderColor: 'rgba(54, 162, 235, 1)',
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderWidth: 2,
                tension: 0.1,
                fill: true,
            }]
        },
        options: {
            ...chartOptions,
            scales: {
                ...chartOptions.scales,
                y: {
                    title: {
                        display: true,
                        text: 'Độ ẩm (%)'
                    },
                    min: 0,
                    max: 100
                }
            }
        }
    });
    
    const soilCtx = document.getElementById('soil-chart').getContext('2d');
    soilMoistureChart = new Chart(soilCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Độ ẩm đất (%)',
                data: [],
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderWidth: 2,
                tension: 0.1,
                fill: true,
            }]
        },
        options: {
            ...chartOptions,
            scales: {
                ...chartOptions.scales,
                y: {
                    title: {
                        display: true,
                        text: 'Độ ẩm đất (%)'
                    },
                    min: 0,
                    max: 100
                }
            }
        }
    });
    
    const lightCtx = document.getElementById('light-chart').getContext('2d');
    lightLevelChart = new Chart(lightCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Ánh sáng (%)',
                data: [],
                borderColor: 'rgba(255, 206, 86, 1)',
                backgroundColor: 'rgba(255, 206, 86, 0.2)',
                borderWidth: 2,
                tension: 0.1,
                fill: true,
            }]
        },
        options: {
            ...chartOptions,
            scales: {
                ...chartOptions.scales,
                y: {
                    title: {
                        display: true,
                        text: 'Ánh sáng (%)'
                    },
                    min: 0,
                    max: 100
                }
            }
        }
    });
}