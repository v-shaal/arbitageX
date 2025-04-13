// ArbitrageX Frontend Script

let analysisPageInitialized = false; // Flag for analysis page init

document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle
    document.getElementById('sidebarCollapse').addEventListener('click', function() {
        document.getElementById('sidebar').classList.toggle('active');
        document.getElementById('content').classList.toggle('active');
    });

    // Page navigation
    const navLinks = document.querySelectorAll('[data-page]');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Reset init flag if navigating AWAY from analysis page
            if (this.getAttribute('data-page') !== 'analysis') {
                analysisPageInitialized = false;
            }
            
            // Get target page
            const targetPage = this.getAttribute('data-page');
            
            // Hide all pages
            document.querySelectorAll('.page-content').forEach(page => {
                page.style.display = 'none';
            });
            
            // Show target page
            const targetPageElement = document.getElementById(`${targetPage}-page`);
            if (targetPageElement) {
                targetPageElement.style.display = 'block';
            }
            
            // Update active state in sidebar
            document.querySelectorAll('#sidebar li').forEach(item => {
                item.classList.remove('active');
            });
            this.closest('li').classList.add('active');
            
            // Initialize page-specific JS only if needed
            if (targetPage === 'analysis') {
                 initAnalysisPage(); // Call init (flag inside will prevent re-runs)
            } else if (targetPage === 'companies') {
                // Example: Initialize companies page if needed
                // initCompaniesPage(); 
            } else if (targetPage === 'strategies') {
                 // Example: Initialize strategies page if needed
                 // initStrategiesPage();
            }
        });
    });

    // Quick action buttons
    const actionButtons = document.querySelectorAll('[data-action]');
    actionButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const action = this.getAttribute('data-action');
            const targetPage = this.getAttribute('data-page');
            
            if (targetPage) {
                // Reset init flag if navigating AWAY from analysis page
                if (targetPage !== 'analysis') {
                    analysisPageInitialized = false;
                }
                
                // Navigate to page first
                document.querySelectorAll('.page-content').forEach(page => {
                    page.style.display = 'none';
                });
                const targetPageElement = document.getElementById(`${targetPage}-page`);
                 if (targetPageElement) {
                    targetPageElement.style.display = 'block';
                 }
                
                // Update active state in sidebar
                document.querySelectorAll('#sidebar li').forEach(item => {
                    item.classList.remove('active');
                });
                 const activeLink = document.querySelector(`#sidebar li a[data-page="${targetPage}"]`);
                 if (activeLink) {
                    activeLink.closest('li').classList.add('active');
                 }
                 
                 // Initialize the target page if navigating via action button
                 if (targetPage === 'analysis') {
                     initAnalysisPage(); // Call init (flag inside will prevent re-runs)
                 }
                 // Add else if for other pages if they need init
            }
            
            // Handle the action (pass the event for context if needed)
            handleAction(action, targetPage, e);
        });
    });

    // Company detail modal (this seems outdated, viewCompanyDetails is used later)
    // const companyViewButtons = document.querySelectorAll('[data-action="view-company"]');
    // companyViewButtons.forEach(button => { ... });

    // CSV upload form submission
    const csvUploadForm = document.getElementById('csvUploadForm');
    if (csvUploadForm) {
        csvUploadForm.addEventListener('submit', async function(e) {
           // ... CSV upload logic ...
        });
    }

    // Strategy upload form submission
    const strategyUploadForm = document.getElementById('strategyUploadForm');
    if (strategyUploadForm) {
        strategyUploadForm.addEventListener('submit', async function(e) {
            // ... Strategy upload logic ...
        });
    }

    // Analysis form submission (This is now handled inside initAnalysisPage)
    // const analysisForm = document.getElementById('analysis-form');
    // if (analysisForm) { ... }

    // Initialize API client
    initApiClient();

    // DO NOT Call initAnalysisPage unconditionally here
    // initAnalysisPage(); 
});

// Handle specific actions
function handleAction(action, targetPage) {
    switch(action) {
        case 'new':
            if (targetPage === 'strategies') {
                // Reset the strategy form
                const strategyForm = document.getElementById('strategyForm');
                if (strategyForm) strategyForm.reset();
                
                // Show the modal
                const strategyModal = new bootstrap.Modal(document.getElementById('newStrategyModal'));
                strategyModal.show();
            }
            break;
            
        case 'upload':
            // No specific action needed, just navigate to upload page
            break;
            
        case 'run':
            if (targetPage === 'analysis') {
                // Focus on analysis form
                document.getElementById('strategySelect').focus();
                
                // Hide results section if visible
                const resultsSection = document.querySelector('#analysisResults');
                if (resultsSection) {
                    resultsSection.style.display = 'none';
                }
            }
            break;
            
        case 'export':
            showNotification('Preparing export...', 'info');
            
            // Get current page context to determine what to export
            let currentPage = null;
            document.querySelectorAll('.page-content').forEach(page => {
                if (page.style.display !== 'none') {
                    currentPage = page.id.replace('-page', '');
                }
            });
            
            if (currentPage === 'analysis') {
                // Export analysis results
                exportAnalysisResults();
            } else if (currentPage === 'companies') {
                // Export companies list
                exportCompanies();
            } else {
                showNotification('Nothing to export from this page', 'warning');
            }
            break;
            
        case 'edit-strategy':
            const strategyId = event.target.getAttribute('data-id');
            editStrategy(strategyId);
            break;
            
        case 'run-strategy':
            const runStrategyId = event.target.getAttribute('data-id');
            runStrategy(runStrategyId);
            break;
            
        case 'view-results':
            const resultsStrategyId = event.target.getAttribute('data-id');
            viewStrategyResults(resultsStrategyId);
            break;
    }
}

// Function to edit a strategy
async function editStrategy(strategyId) {
    try {
        // We only need to get the ID and trigger the correct modal function.
        // showStrategyModal will handle fetching the data and populating its own form.
        showStrategyModal(strategyId);
        
    } catch (error) {
        // Although fetching is moved to showStrategyModal, keep error handling here 
        // in case the ID is invalid or showStrategyModal throws an error immediately.
        console.error('Error initiating strategy edit:', error);
        showNotification(`Error preparing strategy for editing: ${error.message}`, 'danger');
    }
}

// Function to run a strategy
async function runStrategy(strategyId) {
    try {
            // Navigate to analysis page
            document.querySelectorAll('.page-content').forEach(page => {
                page.style.display = 'none';
            });
            document.getElementById('analysis-page').style.display = 'block';
            
            // Update active state in sidebar
            document.querySelectorAll('#sidebar li').forEach(item => {
                item.classList.remove('active');
            });
            document.querySelector('#sidebar li a[data-page="analysis"]').closest('li').classList.add('active');
            
            // Set strategy in dropdown
        document.getElementById('strategySelect').value = strategyId;
        
        // Hide results section if visible
        const resultsSection = document.querySelector('#analysisResults');
        if (resultsSection) {
            resultsSection.style.display = 'none';
        }
        
    } catch (error) {
        console.error('Error running strategy:', error);
        showNotification(`Error: ${error.message}`, 'danger');
    }
}

// Function to view strategy results
async function viewStrategyResults(strategyId) {
    try {
        // Navigate to analysis page
            document.querySelectorAll('.page-content').forEach(page => {
                page.style.display = 'none';
            });
            document.getElementById('analysis-page').style.display = 'block';
            
            // Update active state in sidebar
            document.querySelectorAll('#sidebar li').forEach(item => {
                item.classList.remove('active');
            });
            document.querySelector('#sidebar li a[data-page="analysis"]').closest('li').classList.add('active');
        
        // Set strategy in dropdown
        document.getElementById('strategySelect').value = strategyId;
        
        // Show loading notification
        showNotification('Loading analysis results...', 'info');
        
        // Fetch and display analysis results
        const results = await ApiClient.getAnalysisResults(parseInt(strategyId));
            
            // Show results section
            document.querySelector('#analysisResults').style.display = 'block';
        
        // Render analysis results
        renderAnalysisResults(results, strategyId);
        
        showNotification('Analysis results loaded successfully!', 'success');
        
    } catch (error) {
        console.error('Error viewing strategy results:', error);
        showNotification(`Error: ${error.message}`, 'danger');
    }
}

// Function to export analysis results
function exportAnalysisResults() {
    // In a real implementation, we would call an API endpoint to generate a CSV/Excel
    // For MVP, we'll simulate the export
    
    setTimeout(() => {
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = 'data:text/csv;charset=utf-8,Company,Industry,Score,Explanation\nCompany1,Tech,92%,"Good fit"\nCompany2,Finance,85%,"Strong potential"\n';
        a.download = 'analysis_results.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        showNotification('Results exported successfully!', 'success');
    }, 1500);
}

// Function to export companies list
function exportCompanies() {
    // In a real implementation, we would call an API endpoint to generate a CSV/Excel
    // For MVP, we'll simulate the export
    
    setTimeout(() => {
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = 'data:text/csv;charset=utf-8,Name,Industry,Revenue,Growth,Location\nTechCorp,Software,$45M,22%,Boston\nDataSys,Analytics,$32M,18%,San Francisco\n';
        a.download = 'companies.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        showNotification('Companies exported successfully!', 'success');
    }, 1500);
}

// Show notification
function showNotification(message, type = 'info') {
    // Check if notification container exists
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show`;
    notification.role = 'alert';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Add to container
    container.appendChild(notification);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 150);
    }, 5000);
}

// API Client for backend interactions
const ApiClient = {
    // Base URL for API requests
    baseUrl: '/api',
    
    // Helper method for making API requests
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        let fetchOptions = { ...options }; // Copy options

        // Default headers, handle FormData separately
        let headers = { ...(options.headers || {}) };
        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        } else {
            // Let the browser set the Content-Type for FormData
            delete headers['Content-Type']; 
        }
        fetchOptions.headers = headers;

        try {
            const response = await fetch(url, fetchOptions);
            
            // Handle no content responses (e.g., DELETE)
            if (response.status === 204) {
                return null; 
            }

            // Check if response is JSON before parsing
            const contentType = response.headers.get("content-type");
            let data;
            if (contentType && contentType.indexOf("application/json") !== -1) {
                data = await response.json();
            } else {
                 // Handle non-JSON responses if necessary, or treat as error
            if (!response.ok) {
                    throw new Error(`API request failed with status ${response.status} and non-JSON response`);
            }
                 // If response is OK but not JSON, return null or handle appropriately
            return null;
        }
            
            // Check if request was successful after parsing JSON
            if (!response.ok) {
                throw new Error(data?.detail || `API request failed with status ${response.status}`);
            }
            
            return data;
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            // Re-throw the error so calling functions can handle it
            throw error; 
        }
    },
    
    // Get all strategies
    getStrategies() {
        return this.request('/strategies/');
    },
    
    // Get a single strategy by ID
    getStrategy(id) {
        return this.request(`/strategies/${id}`);
    },
    
    // Create a new strategy
    createStrategy(data) {
        return this.request('/strategies/', {
                method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    // Update an existing strategy
    updateStrategy(id, data) {
        return this.request(`/strategies/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    // Delete a strategy
    deleteStrategy(id) {
        // Note: Backend might not return JSON on DELETE, handled in 'request'
        return this.request(`/strategies/${id}`, { 
            method: 'DELETE'
        }); 
    },

    // Get all companies
    getCompanies() {
        // Corrected: Use request helper, ensure endpoint matches backend if needed
        return this.request('/companies/'); // Assuming backend uses trailing slash
    },

    // Get a single company by ID
    getCompany(id) {
        return this.request(`/companies/${id}`);
    },

    // Get detailed company information (using ID or ticker - ensure backend supports this)
    // Consolidating the two getCompanyDetails methods
    getCompanyDetails(identifier) { 
        // Assuming the backend route can handle both IDs and tickers, 
        // or you might need separate methods if routes differ significantly.
        return this.request(`/companies/${identifier}`); 
    },

    // --- Analysis Operations ---

    // Create a new analysis task
    createAnalysis(strategyId) {
        // Assuming backend expects strategy_id in the body
        return this.request('/analysis/', { // Assuming trailing slash
            method: 'POST',
            body: JSON.stringify({ strategy_id: strategyId })
        });
    },
    
    // Get the status of an analysis task
    getAnalysisStatus(analysisId) {
         // Assuming the backend route is /tasks/{task_id} for status
        return this.request(`/tasks/${analysisId}`);
    },
    
    // Get the results of a completed analysis (using strategy ID)
    getAnalysisResults(strategyId) {
         // Assuming backend route is /analysis/results/{strategy_id}
        return this.request(`/analysis/results/${strategyId}`);
    },

    // --- Task Operations ---

    // Get a specific task by ID
    getTask(taskId) {
        return this.request(`/tasks/${taskId}`);
    },

    // Get multiple tasks with optional filters
    getTasks(agentType = null, taskType = null, status = null, limit = null) {
        const params = new URLSearchParams();
        if (agentType) params.append('agent_type', agentType);
        if (taskType) params.append('task_type', taskType);
        if (status) params.append('status', status);
        if (limit) params.append('limit', limit);
        
        const queryString = params.toString();
        return this.request(`/tasks/${queryString ? '?' + queryString : ''}`); // Append query string if params exist
    },

    // --- Upload Operations ---

    async uploadCSV(file, mappingTemplate) {
        const formData = new FormData();
        // Match the expected field names from the backend endpoint definition
        formData.append('file', file); // Assuming backend expects 'file'
        if (mappingTemplate) {
             // Assuming backend expects 'mapping_template'
            formData.append('mapping_template', mappingTemplate);
        }
        
        // Use request helper for FormData POST
        return this.request('/upload/csv/', { // Assuming trailing slash
            method: 'POST',
            body: formData 
            // Content-Type header is automatically handled by browser for FormData
        });
    },

    async uploadStrategyDocument(file, strategyName) {
        const formData = new FormData();
         // Match the expected field names from the backend endpoint definition
        formData.append('file', file); // Assuming backend expects 'file'
        formData.append('strategy_name', strategyName); // Assuming backend expects 'strategy_name'
        
        // Use request helper for FormData POST
        return this.request('/upload/strategy/', { // Assuming trailing slash
            method: 'POST',
            body: formData
        });
    },

    // --- Health Check ---
    // (Implicitly used by initApiClient which calls request('/health'))

    // --- Agent API endpoints (Example - adjust if needed) ---
    async extractInformation(text) {
        return this.request('/agents/extract-information', { // Assuming route from agent_api.py
            method: 'POST',
            body: JSON.stringify({ text })
        });
    },
    
    // Add other agent endpoints here using this.request if needed...
};

// Initialize API client and load initial data
async function initApiClient() {
    try {
        // Check API health
        const health = await ApiClient.request('/health');
        if (health && health.status === 'healthy') {
            console.log('API connection established');
            
            // Load initial data
            loadInitialData();
        } else {
            console.warn('API health check failed');
            showNotification('API connection failed. Using demo data.', 'warning');
        }
    } catch (error) {
        console.error('API initialization failed:', error);
        showNotification('API connection failed. Using demo data.', 'warning');
    }
}

// Load initial data from API
async function loadInitialData(useFallback = false) {
    try {
        // Fetch companies
        const companies = await ApiClient.getCompanies();
        if (companies && !useFallback) {
            renderCompanies(companies);
        } else {
            console.log('Using fallback company data');
            // Use demo data if API fails
            renderCompanies([
                {
                    id: 1,
                    name: "TechCorp Inc",
                    industry: "Enterprise Software",
                    location: "Boston, MA",
                    employee_count: 120,
                    financial_metrics: [
                        { metric_type: "revenue", value: 45000000, unit: "USD" },
                        { metric_type: "growth_rate", value: 22, unit: "%" }
                    ]
                },
                {
                    id: 2,
                    name: "DataSys",
                    industry: "Data Analytics",
                    location: "San Francisco, CA",
                    employee_count: 85,
                    financial_metrics: [
                        { metric_type: "revenue", value: 32000000, unit: "USD" },
                        { metric_type: "growth_rate", value: 18, unit: "%" }
                    ]
                },
                {
                    id: 3,
                    name: "AICore",
                    industry: "Artificial Intelligence",
                    location: "Austin, TX",
                    employee_count: 65,
                    financial_metrics: [
                        { metric_type: "revenue", value: 28000000, unit: "USD" },
                        { metric_type: "growth_rate", value: 35, unit: "%" }
                    ]
                }
            ]);
        }
        
        // Fetch strategies
        const strategies = await ApiClient.getStrategies();
        if (strategies && !useFallback) {
            renderStrategies(strategies);
        } else {
            console.log('Using fallback strategy data');
            // Use demo data if API fails
            renderStrategies([
                {
                    id: 1,
                    name: "Tech Growth",
                    description: "Focus on high-growth technology companies with strong market position.",
                    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString() // 2 days ago
                },
                {
                    id: 2,
                    name: "Healthcare Innovation",
                    description: "Target healthcare companies with innovative solutions and strong IP.",
                    created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString() // 7 days ago
                },
                {
                    id: 3,
                    name: "Fintech Disruptors",
                    description: "Focus on financial technology companies disrupting traditional banking.",
                    created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString() // 3 days ago
                }
            ]);
        }
        
        // Fetch recent tasks
        const tasks = await ApiClient.getTasks(null, null, 0, 5);
        if (tasks && !useFallback) {
            renderRecentTasks(tasks);
        } else {
            console.log('Using fallback task data');
            // Use demo data if API fails
            renderRecentTasks([
                {
                    id: 1,
                    agent_type: "analysis",
                    task_type: "company_analysis",
                    status: "completed", 
                    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString() // 2 hours ago
                },
                {
                    id: 2,
                    agent_type: "search",
                    task_type: "web_search",
                    status: "completed",
                    created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString() // 5 hours ago
                },
                {
                    id: 3,
                    agent_type: "analysis",
                    task_type: "company_analysis",
                    status: "pending",
                    created_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString() // 1 hour ago
                }
            ]);
        }
        
    } catch (error) {
        console.error('Error loading initial data:', error);
        showNotification('Error loading data. Using demo data.', 'warning');
    }
}

// Render companies in the companies table
function renderCompanies(companies) {
    const tableBody = document.querySelector('#companies-page .table tbody');
    if (!tableBody) return;
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    companies.forEach(company => {
        // Find revenue and growth metrics
        const revenue = company.financial_metrics?.find(m => m.metric_type === 'revenue');
        const growth = company.financial_metrics?.find(m => m.metric_type === 'growth_rate');
        
        // Format revenue
        let revenueFormatted = 'N/A';
        if (revenue) {
            if (revenue.value >= 1000000) {
                revenueFormatted = `$${(revenue.value / 1000000).toFixed(0)}M`;
            } else if (revenue.value >= 1000) {
                revenueFormatted = `$${(revenue.value / 1000).toFixed(0)}K`;
            } else {
                revenueFormatted = `$${revenue.value.toFixed(0)}`;
            }
        }
        
        // Format growth rate
        let growthFormatted = 'N/A';
        if (growth) {
            growthFormatted = `${growth.value.toFixed(1)}%`;
        }
        
        // Calculate strategic fit (randomly for demo)
        // In a real app, this would come from the API
        const strategicFit = Math.floor(50 + Math.random() * 50); // 50-100%
        const fitClass = strategicFit >= 80 ? 'bg-success' : strategicFit >= 60 ? 'bg-warning' : 'bg-danger';
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${company.name}</td>
            <td>${company.industry || 'N/A'}</td>
            <td>${revenueFormatted}</td>
            <td>${growthFormatted}</td>
            <td>${company.location || 'N/A'}</td>
            <td>
                <div class="progress">
                    <div class="progress-bar ${fitClass}" role="progressbar" style="width: ${strategicFit}%;" 
                         aria-valuenow="${strategicFit}" aria-valuemin="0" aria-valuemax="100">${strategicFit}%</div>
                </div>
            </td>
            <td>
                <button class="btn btn-sm btn-outline-primary" data-action="view-company" data-id="${company.id}">View</button>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
    
    // Re-attach event listeners
    document.querySelectorAll('[data-action="view-company"]').forEach(button => {
        button.addEventListener('click', function() {
            const companyId = this.getAttribute('data-id');
            viewCompanyDetails(companyId);
        });
    });
}

// Render strategies in the strategies page
function renderStrategies(strategies) {
    const strategiesContainer = document.querySelector('#strategies-page .card-body .row');
    if (!strategiesContainer) return;
    
    // Clear existing strategies
    strategiesContainer.innerHTML = '';
    
    strategies.forEach(strategy => {
        // Format updated time
        const updatedAt = new Date(strategy.created_at);
        const now = new Date();
        
        let updatedText = '';
        const diffMs = now - updatedAt;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            if (diffHours === 0) {
                updatedText = 'Updated just now';
            } else {
                updatedText = `Updated ${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
            }
        } else if (diffDays === 1) {
            updatedText = 'Updated yesterday';
        } else {
            updatedText = `Updated ${diffDays} days ago`;
        }
        
        // Create strategy card
        const colDiv = document.createElement('div');
        colDiv.className = 'col-md-4 mb-4';
        
        colDiv.innerHTML = `
            <div class="card strategy-card">
                <div class="card-body">
                    <h5 class="card-title">${strategy.name}</h5>
                    <p class="card-text">${strategy.description || 'No description provided'}</p>
                    <div class="strategy-meta">
                        <span><i class="bi bi-building"></i> ? matches</span>
                        <span><i class="bi bi-calendar"></i> ${updatedText}</span>
                    </div>
                    <div class="strategy-actions mt-3">
                        <button class="btn btn-sm btn-outline-primary" data-action="edit-strategy" data-id="${strategy.id}">Edit</button>
                        <button class="btn btn-sm btn-outline-success" data-action="run-strategy" data-id="${strategy.id}">Run</button>
                        <button class="btn btn-sm btn-outline-info" data-action="view-results" data-id="${strategy.id}">Results</button>
                    </div>
                </div>
            </div>
        `;
        
        strategiesContainer.appendChild(colDiv);
    });
    
    // Re-attach event listeners
    document.querySelectorAll('[data-action="edit-strategy"]').forEach(button => {
        button.addEventListener('click', function() {
            const strategyId = this.getAttribute('data-id');
            editStrategy(strategyId);
        });
    });
    
    document.querySelectorAll('[data-action="run-strategy"]').forEach(button => {
        button.addEventListener('click', function() {
            const strategyId = this.getAttribute('data-id');
            runStrategy(strategyId);
        });
    });
    
    document.querySelectorAll('[data-action="view-results"]').forEach(button => {
        button.addEventListener('click', function() {
            const strategyId = this.getAttribute('data-id');
            viewStrategyResults(strategyId);
        });
    });
}

// Render recent tasks in the dashboard
function renderRecentTasks(tasks) {
    const activityList = document.querySelector('.activity-list');
    if (!activityList) return;
    
    // Clear existing activities
    activityList.innerHTML = '';
    
    tasks.forEach(task => {
        // Format time
        const createdAt = new Date(task.created_at);
        const now = new Date();
        
        let timeText = '';
        const diffMs = now - createdAt;
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        
        if (diffHours < 1) {
            const diffMinutes = Math.floor(diffMs / (1000 * 60));
            timeText = `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
        } else if (diffHours < 24) {
            timeText = `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
        } else {
            const diffDays = Math.floor(diffHours / 24);
            if (diffDays === 1) {
                timeText = 'Yesterday';
            } else {
                timeText = `${diffDays} days ago`;
            }
        }
        
        // Set icon and text based on task type
        let icon, text, bgClass;
        
        if (task.agent_type === 'analysis') {
            icon = 'bi-graph-up';
            bgClass = 'bg-success';
            text = `Analysis task ${task.status}`;
        } else if (task.agent_type === 'search') {
            icon = 'bi-search';
            bgClass = 'bg-info';
            text = `Search query ${task.status}`;
        } else {
            icon = 'bi-gear';
            bgClass = 'bg-primary';
            text = `Task ${task.status}`;
        }
        
        const listItem = document.createElement('li');
        listItem.className = 'activity-item';
        listItem.innerHTML = `
            <div class="activity-icon ${bgClass}"><i class="bi ${icon}"></i></div>
            <div class="activity-content">
                <p class="activity-text">${text}</p>
                <p class="activity-time">${timeText}</p>
            </div>
        `;
        
        activityList.appendChild(listItem);
    });
}

// Helper function to view company details
async function viewCompanyDetails(companyId) {
    try {
        const company = await ApiClient.getCompany(companyId);
        if (!company) {
            throw new Error('Company not found');
        }
        
        // Update modal title
        document.getElementById('companyDetailModalLabel').textContent = company.name;
        
        // Update overview tab
        const overviewTab = document.getElementById('overview');
        if (overviewTab) {
            // Find financial metrics
            const revenue = company.financial_metrics?.find(m => m.metric_type === 'revenue');
            const growth = company.financial_metrics?.find(m => m.metric_type === 'growth_rate');
            
            // Format revenue
            let revenueFormatted = 'N/A';
            if (revenue) {
                if (revenue.value >= 1000000) {
                    revenueFormatted = `$${(revenue.value / 1000000).toFixed(0)}M`;
                } else if (revenue.value >= 1000) {
                    revenueFormatted = `$${(revenue.value / 1000).toFixed(0)}K`;
                } else {
                    revenueFormatted = `$${revenue.value.toFixed(0)}`;
                }
            }
            
            overviewTab.querySelector('.row:first-child').innerHTML = `
                <div class="col-md-6">
                    <p><strong>Founded:</strong> ${company.founding_date ? new Date(company.founding_date).getFullYear() : 'N/A'}</p>
                    <p><strong>Location:</strong> ${company.location || 'N/A'}</p>
                    <p><strong>Employees:</strong> ${company.employee_count || 'N/A'}</p>
                    <p><strong>Industry:</strong> ${company.industry || 'N/A'}</p>
                </div>
                <div class="col-md-6">
                    <p><strong>Website:</strong> <a href="${company.website || '#'}" target="_blank">${company.website || 'N/A'}</a></p>
                    <p><strong>Revenue:</strong> ${revenueFormatted}</p>
                    <p><strong>Growth Rate:</strong> ${growth ? growth.value.toFixed(1) + '%' : 'N/A'}</p>
                </div>
            `;
            
            // Update description
            const descriptionDiv = overviewTab.querySelector('.row.mt-3 .col-md-12 p');
            if (descriptionDiv) {
                descriptionDiv.textContent = company.description || 'No description available.';
            }
        }
        
        // Show the modal
            const companyModal = new bootstrap.Modal(document.getElementById('companyDetailModal'));
            companyModal.show();
        
    } catch (error) {
        console.error('Error viewing company details:', error);
        showNotification(`Error: ${error.message}`, 'danger');
    }
}

// Function to render analysis results
function renderAnalysisResults(results, strategyId) {
    const resultsContainer = document.getElementById('analysis-results');
    if (!resultsContainer) return;
    
    // Get strategy details for the title
    ApiClient.getStrategy(strategyId)
        .then(strategy => {
            // Create results content
            let content = `
                <div class="results-header">
                    <h2>Analysis Results: ${strategy.name}</h2>
                    <p class="timestamp">Completed on: ${new Date().toLocaleString()}</p>
                </div>
            `;
            
            if (!results.companies || results.companies.length === 0) {
                content += `<p class="no-results">No matching companies found for this strategy.</p>`;
            } else {
                // Sort companies by score in descending order
                const sortedCompanies = [...results.companies].sort((a, b) => b.score - a.score);
                
                content += `
                    <div class="results-summary">
                        <p>Found ${sortedCompanies.length} companies matching the strategy criteria.</p>
                    </div>
                    <table class="results-table">
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>Company</th>
                                <th>Score</th>
                                <th>Market Cap</th>
                                <th>P/E Ratio</th>
                                <th>Revenue Growth</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                sortedCompanies.forEach((company, index) => {
                    content += `
                        <tr>
                            <td>${index + 1}</td>
                            <td>${company.name}</td>
                            <td><span class="score-badge">${company.score.toFixed(1)}</span></td>
                            <td>${formatCurrency(company.market_cap)}</td>
                            <td>${company.pe_ratio ? company.pe_ratio.toFixed(2) : 'N/A'}</td>
                            <td>${company.revenue_growth ? company.revenue_growth.toFixed(2) + '%' : 'N/A'}</td>
                            <td>
                                <button class="btn-view" onclick="viewCompany('${company.id}')">View</button>
                            </td>
                        </tr>
                    `;
                });
                
                content += `
                        </tbody>
                    </table>
                `;
            }
            
            resultsContainer.innerHTML = content;
        })
        .catch(error => {
            console.error('Error fetching strategy details:', error);
            resultsContainer.innerHTML = `<div class="error-message"><p>Error loading results: ${error.message}</p></div>`;
        });
}

// Function to view company details
function viewCompany(companyId) {
    ApiClient.getCompany(companyId)
        .then(company => {
            // Create modal for company details
            const modal = document.createElement('div');
            modal.className = 'modal';
            
            // Financial metrics
            const financials = [
                { label: 'Market Cap', value: formatCurrency(company.market_cap) },
                { label: 'P/E Ratio', value: company.pe_ratio ? company.pe_ratio.toFixed(2) : 'N/A' },
                { label: 'EPS', value: company.eps ? company.eps.toFixed(2) : 'N/A' },
                { label: 'Revenue', value: formatCurrency(company.revenue) },
                { label: 'Revenue Growth', value: company.revenue_growth ? company.revenue_growth.toFixed(2) + '%' : 'N/A' },
                { label: 'Profit Margin', value: company.profit_margin ? company.profit_margin.toFixed(2) + '%' : 'N/A' },
                { label: 'Debt-to-Equity', value: company.debt_to_equity ? company.debt_to_equity.toFixed(2) : 'N/A' },
                { label: 'ROE', value: company.roe ? company.roe.toFixed(2) + '%' : 'N/A' },
                { label: 'ROA', value: company.roa ? company.roa.toFixed(2) + '%' : 'N/A' },
                { label: 'Current Ratio', value: company.current_ratio ? company.current_ratio.toFixed(2) : 'N/A' }
            ];
            
            const financialsHtml = financials
                .map(item => `<div class="metric"><span class="label">${item.label}:</span> <span class="value">${item.value}</span></div>`)
                .join('');
            
            modal.innerHTML = `
                <div class="modal-content">
                    <span class="close-modal">&times;</span>
                    <div class="company-header">
                        <h2>${company.name}</h2>
                        <div class="company-meta">
                            <span class="ticker">${company.ticker}</span>
                            <span class="industry">${company.industry || 'N/A'}</span>
                            <span class="location">${company.location || 'N/A'}</span>
                            ${company.founded ? `<span class="founded">Founded: ${company.founded}</span>` : ''}
                        </div>
                    </div>
                    
                    <div class="company-body">
                        <div class="company-financials">
                            <h3>Financial Information</h3>
                            <div class="metrics-grid">
                                ${financialsHtml}
                            </div>
                        </div>
                        
                        <div class="company-description">
                            <h3>Description</h3>
                            <p>${company.description || 'No description available.'}</p>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Show modal
            setTimeout(() => {
                modal.classList.add('show');
            }, 10);
            
            // Close modal when clicking the X or outside the modal
            const closeBtn = modal.querySelector('.close-modal');
            closeBtn.addEventListener('click', () => {
                modal.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(modal);
                }, 300);
            });
            
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('show');
                    setTimeout(() => {
                        document.body.removeChild(modal);
                    }, 300);
                }
            });
        })
        .catch(error => {
            console.error('Error fetching company details:', error);
            showNotification('Error loading company details: ' + error.message, 'error');
        });
}

// Helper function to format currency
function formatCurrency(value) {
    if (!value && value !== 0) return 'N/A';
    
    // If value is greater than 1 million, show as millions
    if (Math.abs(value) >= 1000000) {
        return `$${(value / 1000000).toFixed(1)}M`;
    }
    
    // If value is greater than 1 thousand, show as thousands
    if (Math.abs(value) >= 1000) {
        return `$${(value / 1000).toFixed(1)}K`;
    }
    
    // Otherwise show the actual value
    return `$${value.toFixed(2)}`;
}

// Populate strategy dropdown with available strategies
async function populateStrategyDropdown(selectElement) {
    // Show loading state
    selectElement.innerHTML = '<option value="">Loading strategies...</option>';
    selectElement.disabled = true;
    
    try {
        const strategies = await ApiClient.getStrategies();
        
        // Clear loading state
        selectElement.innerHTML = '';
        
        if (strategies.length === 0) {
            // No strategies available
            selectElement.innerHTML = '<option value="">No strategies available</option>';
        } else {
            // Add default option
            selectElement.innerHTML = '<option value="">Select a strategy</option>';
            
            // Add each strategy as an option
            strategies.forEach(strategy => {
                const option = document.createElement('option');
                option.value = strategy.id;
                option.textContent = strategy.name;
                selectElement.appendChild(option);
            });
        }
    } catch (error) {
        // Handle error
        selectElement.innerHTML = '<option value="">Error loading strategies</option>';
        showNotification('Failed to load strategies', 'error');
    } finally {
        // Re-enable select element
        selectElement.disabled = false;
    }
}

// Initialize the analysis page
function initAnalysisPage() {
    // Prevent multiple initializations
    if (analysisPageInitialized) {
        console.log("Analysis page already initialized. Skipping.");
        return;
    }
    analysisPageInitialized = true;
    console.log("Initializing analysis page...");

    // Get elements ONCE during initialization
    const strategySelect = document.getElementById('strategySelect');
    const analysisForm = document.getElementById('analysisForm');
    const newStrategyBtn = document.getElementById('newStrategyBtn');
    const editStrategyBtn = document.getElementById('editStrategyBtn');
    // const resultsContainer = document.getElementById('resultsContainer'); // Get inside handlers
    // const detailsContainer = document.getElementById('strategyDetails'); // Get inside handlers

    // Basic check if essential elements exist
    if (!strategySelect || !analysisForm) {
        console.error("Essential analysis page elements (select/form) not found during init!");
        analysisPageInitialized = false; // Allow re-init if page reloads
        return;
    }
    
    // Populate strategy dropdown
    populateStrategyDropdown(strategySelect);
    
    // --- Event Listeners --- 
    // Attach listeners only ONCE

    // Show strategy details when selected
    strategySelect.addEventListener('change', async function() {
        console.log("Strategy selection changed...");
        // Query for potentially dynamic containers INSIDE the handler
        const currentResultsContainer = document.getElementById('resultsContainer'); 
        const currentDetailsContainer = document.getElementById('strategyDetails');
        const currentEditStrategyBtn = document.getElementById('editStrategyBtn');
        const currentRunAnalysisBtn = document.getElementById('runAnalysisBtn');

        // Check if containers exist before modifying
        if (!currentResultsContainer) {
            console.error("Change Handler Error: #resultsContainer not found.");
            return; 
        }
        // No need to return if details/buttons missing, just log
        if (!currentDetailsContainer) console.warn("Change Handler Warning: #strategyDetails not found.");
        if (!currentEditStrategyBtn) console.warn("Change Handler Warning: #editStrategyBtn not found.");
        if (!currentRunAnalysisBtn) console.warn("Change Handler Warning: #runAnalysisBtn not found.");
        
        currentResultsContainer.innerHTML = ''; // Clear previous results
        if (currentEditStrategyBtn) currentEditStrategyBtn.style.display = 'none'; // Hide edit button
        
        const strategyId = this.value;
        
        if (strategyId) {
            if(currentRunAnalysisBtn) currentRunAnalysisBtn.disabled = false; // Enable run button
            if (currentEditStrategyBtn) currentEditStrategyBtn.style.display = 'inline-block'; // Show edit button
            
            try {
                const strategy = await ApiClient.getStrategy(strategyId);
                if (currentDetailsContainer) {
                    // ... (logic to display strategy details in currentDetailsContainer) ...
                    currentDetailsContainer.innerHTML = `<h4>Strategy Details</h4><p>...</p>`; // Simplified example
                } else {
                    showNotification('Cannot display strategy details (UI element missing).', 'warning');
                }
            } catch (error) {
                showNotification('Failed to load strategy details', 'error');
                if (currentDetailsContainer) currentDetailsContainer.innerHTML = ''; // Clear on error
            }
        } else {
            if (currentDetailsContainer) currentDetailsContainer.innerHTML = ''; // Clear details
            if (currentRunAnalysisBtn) currentRunAnalysisBtn.disabled = true; // Disable run button
        }
    });
    
    // Run analysis button handler
    analysisForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        console.log("Analysis form submitted...");

        const currentStrategySelect = document.getElementById('strategySelect'); // Re-get in handler
        const strategyId = currentStrategySelect ? currentStrategySelect.value : null;
        
        if (!strategyId) {
            showNotification('Please select a strategy', 'warning');
            return;
        }

        // Get elements needed for submit action
        const runBtn = document.getElementById('runAnalysisBtn'); 
        const resultsContainer = document.getElementById('resultsContainer');

        if (!runBtn) {
            console.error("Submit Handler Error: Could not find #runAnalysisBtn in the document."); 
            showNotification('Internal UI error: Cannot find run button.', 'danger');
            return;
        }
        if (!resultsContainer) {
            console.error("Submit Handler Error: Could not find #resultsContainer.");
            showNotification('Internal UI error: Cannot find results display area.', 'danger');
            return;
        }

        let originalBtnText = runBtn.textContent; // Store original text
        runBtn.disabled = true;
        runBtn.textContent = 'Running Analysis...';
        resultsContainer.innerHTML = '<div class="loading-spinner"></div><p>Running analysis, please wait...</p>';
        
        try {
            const analysisTask = await ApiClient.createAnalysis(strategyId);
            await pollAnalysisStatus(analysisTask.task_id, resultsContainer);
        } catch (error) {
            const errorMessage = error.message || 'Unknown error occurred';
            resultsContainer.innerHTML = `<div class="error-message">Analysis failed: ${errorMessage}</div>`;
            showNotification(`Analysis failed: ${errorMessage}`, 'error');
        } finally {
            // Reset button state using the stored text
            // Re-find button in case DOM changed, though less likely here
            const finalRunBtn = document.getElementById('runAnalysisBtn'); 
            if (finalRunBtn) {
                 finalRunBtn.disabled = false;
                 finalRunBtn.textContent = originalBtnText;
            } else {
                console.error("Submit Handler Error: runBtn became null unexpectedly before resetting state.");
            }
        }
    });
    
    // New strategy button handler
    if (newStrategyBtn) {
        // Check if listener already exists (simple check)
        if (!newStrategyBtn.dataset.listenerAttached) {
             newStrategyBtn.addEventListener('click', function() {
                showStrategyModal();
             });
             newStrategyBtn.dataset.listenerAttached = 'true';
        }
    }
    
    // Edit strategy button handler
    if (editStrategyBtn) {
         // Check if listener already exists
        if (!editStrategyBtn.dataset.listenerAttached) {
             editStrategyBtn.addEventListener('click', function() {
                const currentStrategySelect = document.getElementById('strategySelect'); // Re-get in handler
                const strategyId = currentStrategySelect ? currentStrategySelect.value : null;
                if (strategyId) {
                    showStrategyModal(strategyId);
                }
             });
             editStrategyBtn.dataset.listenerAttached = 'true';
        }
    }
    console.log("Analysis page initialization complete.");
}

// Poll the analysis status
async function pollAnalysisStatus(analysisId, resultsContainer) {
    const maxAttempts = 60; // 5 minutes (5s intervals)
    let attempts = 0;
    
    return new Promise((resolve, reject) => {
        const checkStatus = async () => {
            try {
                const status = await ApiClient.getAnalysisStatus(analysisId);
                
                if (status.status === 'completed') {
                    // Analysis completed successfully
                    displayAnalysisResults(status, resultsContainer);
                    resolve(status);
                } else if (status.status === 'failed') {
                    // Analysis failed
                    resultsContainer.innerHTML = `<div class="error-message">Analysis failed: ${status.error || 'Unknown error'}</div>`;
                    reject(new Error(status.error || 'Analysis failed'));
                } else {
                    // Analysis still running
                    attempts++;
                    
                    if (attempts >= maxAttempts) {
                        resultsContainer.innerHTML = '<div class="error-message">Analysis timed out. Please check the status later.</div>';
                        reject(new Error('Analysis timed out'));
                    } else {
                        // Update progress if available
                        if (status.progress) {
                            resultsContainer.innerHTML = `
                                <div class="loading-spinner"></div>
                                <p>Running analysis: ${status.progress}% complete</p>
                            `;
                        }
                        
                        // Check again after 5 seconds
                        setTimeout(checkStatus, 5000);
                    }
                }
            } catch (error) {
                resultsContainer.innerHTML = `<div class="error-message">Failed to check analysis status: ${error.message}</div>`;
                reject(error);
            }
        };
        
        // Start checking
        checkStatus();
    });
}

// Display analysis results
function displayAnalysisResults(analysis, container) {
    const results = analysis.results || [];
    
    if (results.length === 0) {
        container.innerHTML = '<div class="info-message">No companies matched the strategy criteria.</div>';
        return;
    }
    
    // Build results HTML
    let html = `
        <h3>Analysis Results</h3>
        <p>${results.length} companies matched your criteria</p>
        <div class="results-table-container">
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Company Name</th>
                        <th>Market Cap</th>
                        <th>P/E Ratio</th>
                        <th>Revenue Growth</th>
                        <th>Profit Margin</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    // Add each result row
    results.forEach(company => {
        html += `
            <tr>
                <td>${company.ticker}</td>
                <td>${company.name}</td>
                <td>$${(company.market_cap || 0).toLocaleString()}</td>
                <td>${company.pe_ratio ? company.pe_ratio.toFixed(2) : 'N/A'}</td>
                <td>${company.revenue_growth ? (company.revenue_growth * 100).toFixed(2) + '%' : 'N/A'}</td>
                <td>${company.profit_margin ? (company.profit_margin * 100).toFixed(2) + '%' : 'N/A'}</td>
                <td>
                    <button class="btn-small view-details" data-ticker="${company.ticker}">Details</button>
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    // Update container
    container.innerHTML = html;
    
    // Add event listeners to detail buttons
    const detailButtons = container.querySelectorAll('.view-details');
    detailButtons.forEach(button => {
        button.addEventListener('click', function() {
            const ticker = this.getAttribute('data-ticker');
            showCompanyDetails(ticker);
        });
    });
}

// Show company details modal
async function showCompanyDetails(ticker) {
    try {
        // Create modal container
        const modalContainer = document.createElement('div');
        modalContainer.className = 'modal-container';
        modalContainer.innerHTML = `
            <div class="modal company-modal">
                <div class="modal-header">
                    <h3>Loading company details...</h3>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="loading-spinner"></div>
                </div>
            </div>
        `;
        
        // Add to document
        document.body.appendChild(modalContainer);
        
        // Add close event
        const closeBtn = modalContainer.querySelector('.close-modal');
        closeBtn.addEventListener('click', function() {
            document.body.removeChild(modalContainer);
        });
        
        // Fetch company details
        const company = await ApiClient.getCompanyDetails(ticker);
        
        // Update modal content
        const modalHeader = modalContainer.querySelector('.modal-header h3');
        const modalBody = modalContainer.querySelector('.modal-body');
        
        modalHeader.textContent = `${company.name} (${company.ticker})`;
        
        modalBody.innerHTML = `
            <div class="company-details">
                <div class="company-overview">
                    <p><strong>Sector:</strong> ${company.sector || 'N/A'}</p>
                    <p><strong>Industry:</strong> ${company.industry || 'N/A'}</p>
                    <p><strong>Market Cap:</strong> $${(company.market_cap || 0).toLocaleString()}</p>
                    <p><strong>Exchange:</strong> ${company.exchange || 'N/A'}</p>
                </div>
                
                <div class="financial-metrics">
                    <h4>Financial Metrics</h4>
                    <div class="metrics-grid">
                        <div class="metric">
                            <span class="metric-name">P/E Ratio</span>
                            <span class="metric-value">${company.pe_ratio ? company.pe_ratio.toFixed(2) : 'N/A'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-name">Revenue Growth</span>
                            <span class="metric-value">${company.revenue_growth ? (company.revenue_growth * 100).toFixed(2) + '%' : 'N/A'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-name">Profit Margin</span>
                            <span class="metric-value">${company.profit_margin ? (company.profit_margin * 100).toFixed(2) + '%' : 'N/A'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-name">Debt/Equity</span>
                            <span class="metric-value">${company.debt_to_equity ? company.debt_to_equity.toFixed(2) : 'N/A'}</span>
                        </div>
                    </div>
                </div>
                
                <div class="company-description">
                    <h4>Business Description</h4>
                    <p>${company.description || 'No description available.'}</p>
                </div>
            </div>
        `;
    } catch (error) {
        showNotification(`Failed to load details for ${ticker}`, 'error');
        console.error('Error fetching company details:', error);
    }
}

// Show modal for creating or editing strategies
async function showStrategyModal(strategyId = null) {
    const isEdit = strategyId !== null;
    let strategy = null;
    
    if (isEdit) {
        try {
            strategy = await ApiClient.getStrategy(strategyId);
        } catch (error) {
            showNotification('Failed to load strategy for editing', 'error');
            return;
        }
    }
    
    // Create modal container
    const modalContainer = document.createElement('div');
    modalContainer.className = 'modal-container';
    modalContainer.innerHTML = `
        <div class="modal strategy-modal">
            <div class="modal-header">
                <h3>${isEdit ? 'Edit Strategy' : 'Create New Strategy'}</h3>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="strategyForm">
                    <div class="form-group">
                        <label for="strategyName">Strategy Name</label>
                        <input type="text" id="strategyName" value="${isEdit ? strategy.name : ''}" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="strategyDescription">Description</label>
                        <textarea id="strategyDescription">${isEdit ? strategy.description || '' : ''}</textarea>
                    </div>
                    
                    <h4>Criteria</h4>
                    
                    <div class="criteria-section">
                        <h5>Market Cap (USD)</h5>
                        <div class="form-row">
                            <div class="form-group half">
                                <label for="marketCapMin">Minimum</label>
                                <input type="number" id="marketCapMin" value="${isEdit && strategy.market_cap_min ? strategy.market_cap_min : ''}" min="0">
                            </div>
                            <div class="form-group half">
                                <label for="marketCapMax">Maximum</label>
                                <input type="number" id="marketCapMax" value="${isEdit && strategy.market_cap_max ? strategy.market_cap_max : ''}" min="0">
                            </div>
                        </div>
                    </div>
                    
                    <div class="criteria-section">
                        <h5>P/E Ratio</h5>
                        <div class="form-row">
                            <div class="form-group half">
                                <label for="peRatioMin">Minimum</label>
                                <input type="number" id="peRatioMin" value="${isEdit && strategy.pe_ratio_min ? strategy.pe_ratio_min : ''}" min="0" step="0.01">
                            </div>
                            <div class="form-group half">
                                <label for="peRatioMax">Maximum</label>
                                <input type="number" id="peRatioMax" value="${isEdit && strategy.pe_ratio_max ? strategy.pe_ratio_max : ''}" min="0" step="0.01">
                            </div>
                        </div>
                    </div>
                    
                    <div class="criteria-section">
                        <h5>Revenue Growth (%)</h5>
                        <div class="form-group">
                            <label for="revenueGrowthMin">Minimum</label>
                            <input type="number" id="revenueGrowthMin" value="${isEdit && strategy.revenue_growth_min ? strategy.revenue_growth_min : ''}" step="0.1">
                        </div>
                    </div>
                    
                    <div class="criteria-section">
                        <h5>Profit Margin (%)</h5>
                        <div class="form-group">
                            <label for="profitMarginMin">Minimum</label>
                            <input type="number" id="profitMarginMin" value="${isEdit && strategy.profit_margin_min ? strategy.profit_margin_min : ''}" step="0.1">
                        </div>
                    </div>
                    
                    <div class="form-actions">
                        <button type="button" class="btn-secondary cancel-btn">Cancel</button>
                        <button type="submit" class="btn-primary">${isEdit ? 'Update Strategy' : 'Create Strategy'}</button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    // Add to document
    document.body.appendChild(modalContainer);
    
    // Add close events
    const closeBtn = modalContainer.querySelector('.close-modal');
    const cancelBtn = modalContainer.querySelector('.cancel-btn');
    const closeModal = () => {
        document.body.removeChild(modalContainer);
    };
    
    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    
    // Form submission
    const form = modalContainer.querySelector('#strategyForm');
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Get form values
        const data = {
            name: document.getElementById('strategyName').value,
            description: document.getElementById('strategyDescription').value,
            market_cap_min: document.getElementById('marketCapMin').value ? Number(document.getElementById('marketCapMin').value) : null,
            market_cap_max: document.getElementById('marketCapMax').value ? Number(document.getElementById('marketCapMax').value) : null,
            pe_ratio_min: document.getElementById('peRatioMin').value ? Number(document.getElementById('peRatioMin').value) : null,
            pe_ratio_max: document.getElementById('peRatioMax').value ? Number(document.getElementById('peRatioMax').value) : null,
            revenue_growth_min: document.getElementById('revenueGrowthMin').value ? Number(document.getElementById('revenueGrowthMin').value) : null,
            profit_margin_min: document.getElementById('profitMarginMin').value ? Number(document.getElementById('profitMarginMin').value) : null
        };
        
        // Disable form
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = isEdit ? 'Updating...' : 'Creating...';
        
        try {
            if (isEdit) {
                // Update existing strategy
                await ApiClient.updateStrategy(strategyId, data);
                showNotification('Strategy updated successfully', 'success');
            } else {
                // Create new strategy
                await ApiClient.createStrategy(data);
                showNotification('Strategy created successfully', 'success');
            }
            
            // Close modal
            closeModal();
            
            // Refresh strategy dropdown
            const strategySelect = document.getElementById('strategySelect');
            if (strategySelect) {
                populateStrategyDropdown(strategySelect);
            }
        } catch (error) {
            showNotification(isEdit ? 'Failed to update strategy' : 'Failed to create strategy', 'error');
        } finally {
            // Re-enable button
            submitBtn.disabled = false;
            submitBtn.textContent = originalBtnText;
        }
    });
}
