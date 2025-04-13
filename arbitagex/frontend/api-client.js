// API Client for connecting to backend
const ApiClient = {
    // Use relative URL to work with any deployment environment
    baseUrl: '',
    
    async get(endpoint) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`);
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            showNotification(`API request failed: ${error.message}`, 'danger');
            return null;
        }
    },
    
    async post(endpoint, data) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            showNotification(`API request failed: ${error.message}`, 'danger');
            return null;
        }
    },
    
    async uploadFile(endpoint, formData) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            showNotification(`API request failed: ${error.message}`, 'danger');
            return null;
        }
    },

    // Companies endpoints
    async getCompanies(skip = 0, limit = 100) {
        return await this.get(`/api/companies/?skip=${skip}&limit=${limit}`);
    },

    async getCompany(id) {
        return await this.get(`/api/companies/${id}`);
    },

    async createCompany(companyData) {
        return await this.post('/api/companies/', companyData);
    },

    // Strategy endpoints
    async getStrategies(skip = 0, limit = 100) {
        return await this.get(`/api/strategies/?skip=${skip}&limit=${limit}`);
    },

    async getStrategy(id) {
        return await this.get(`/api/strategies/${id}`);
    },

    async createStrategy(strategyData) {
        return await this.post('/api/strategies/', strategyData);
    },

    // Upload endpoints
    async uploadCSV(file, mappingTemplate = null) {
        const formData = new FormData();
        formData.append('file', file);
        
        if (mappingTemplate) {
            formData.append('mapping_template', mappingTemplate);
        }
        
        return await this.uploadFile('/api/upload/csv/', formData);
    },

    async uploadStrategyDocument(file, strategyName) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('strategy_name', strategyName);
        
        return await this.uploadFile('/api/upload/strategy/', formData);
    },

    // Search endpoints
    async createSearch(query, targetEntity = null) {
        return await this.post('/api/search/', {
            query,
            target_entity: targetEntity
        });
    },

    async getSearchResults(searchId) {
        return await this.get(`/api/search/${searchId}/results`);
    },

    // Analysis endpoints
    async createAnalysis(strategyId, filters = {}) {
        return await this.post('/api/analysis/', {
            strategy_id: strategyId,
            filters
        });
    },

    async getAnalysisResults(strategyId) {
        return await this.get(`/api/analysis/results/${strategyId}`);
    },

    // Agent Task endpoints
    async getTask(taskId) {
        return await this.get(`/api/tasks/${taskId}`);
    },

    async getTasks(agentType = null, status = null, skip = 0, limit = 100) {
        let url = `/api/tasks/?skip=${skip}&limit=${limit}`;
        
        if (agentType) {
            url += `&agent_type=${agentType}`;
        }
        
        if (status) {
            url += `&status=${status}`;
        }
        
        return await this.get(url);
    },

    // Agent API endpoints
    async extractInformation(text) {
        return await this.post('/api/agents/extract-information', { text });
    },
    
    async generateProfile(companyName, texts) {
        return await this.post('/api/agents/generate-profile', { 
            company_name: companyName, 
            texts 
        });
    }
};

// Initialize API client and load initial data
async function initApiClient() {
    try {
        // Check API health
        const health = await ApiClient.get('/api/health');
        if (health && health.status === 'healthy') {
            console.log('API connection established');
            
            // Load initial data
            loadInitialData();
        } else {
            console.warn('API health check failed');
            showNotification('API connection failed. Using demo data.', 'warning');
            // Still attempt to load data in case we have fallbacks
            loadInitialData(true);
        }
    } catch (error) {
        console.error('API initialization failed:', error);
        showNotification('API connection failed. Using demo data.', 'warning');
        // Still attempt to load data with fallbacks
        loadInitialData(true);
    }
}
