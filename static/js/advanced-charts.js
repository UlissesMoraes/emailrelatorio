/**
 * advanced-charts.js - Advanced visualization for Email Report Management System
 * 
 * This file contains functions for creating advanced charts and data visualizations:
 * - Hourly activity chart
 * - Contact bubble chart
 * - Word cloud visualization
 * - Email metrics radar chart
 * - Activity heatmap
 */

// Main initialization function for all advanced charts
function initializeAdvancedCharts(data) {
    if (!data) {
        console.error('Nenhum dado disponível para os gráficos avançados');
        
        // Mostrar mensagens de erro para cada gráfico
        showNoDataMessage('hourlyActivityChart', 'Atividade por Hora');
        showNoDataMessage('contactBubbleChart', 'Principais Contatos');
        showNoDataMessage('subjectWordCloudContainer', 'Termos Mais Frequentes');
        showNoDataMessage('emailMetricsChart', 'Métricas de Comunicação');
        showNoDataMessage('activityHeatmapChart', 'Mapa de Atividade');
        return;
    }
    
    console.log('Inicializando gráficos avançados com dados:', data);
    
    try {
        // Create hourly activity chart - check for proper structure
        if (data.hourly_activity && Array.isArray(data.hourly_activity)) {
            createHourlyActivityChart(data.hourly_activity);
        } else {
            showNoDataMessage('hourlyActivityChart', 'Atividade por Hora');
        }
        
        // Create contact bubble chart
        if (data.contact_data && Array.isArray(data.contact_data) && data.contact_data.length > 0) {
            createContactBubbleChart(data.contact_data);
        } else {
            showNoDataMessage('contactBubbleChart', 'Principais Contatos');
        }
        
        // Create word cloud visualization
        if (data.word_cloud && Array.isArray(data.word_cloud) && data.word_cloud.length > 0) {
            createWordCloudVisualization(data.word_cloud);
        } else {
            showNoDataMessage('subjectWordCloudContainer', 'Termos Mais Frequentes');
        }
        
        // Create email metrics radar chart
        if (data.email_metrics && data.email_metrics.labels && data.email_metrics.datasets) {
            createEmailMetricsRadarChart(data.email_metrics);
        } else {
            showNoDataMessage('emailMetricsChart', 'Métricas de Comunicação');
        }
        
        // Create activity heatmap
        if (data.activity_heatmap && Array.isArray(data.activity_heatmap) && data.activity_heatmap.length > 0) {
            createActivityHeatmap(data.activity_heatmap);
        } else {
            showNoDataMessage('activityHeatmapChart', 'Mapa de Atividade');
        }
    } catch (error) {
        console.error('Erro ao inicializar gráficos avançados:', error);
    }
}

// Função para mostrar mensagem quando não há dados disponíveis
function showNoDataMessage(elementId, chartTitle) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const container = element.parentNode;
    container.innerHTML = `
        <div class="chart-placeholder">
            <i class="fas fa-chart-bar"></i>
            <p>Dados insuficientes para gerar o gráfico de ${chartTitle}.</p>
            <small>Sincronize mais e-mails ou realize mais atividades para visualizar este gráfico.</small>
        </div>
    `;
}

// Hourly activity chart
function createHourlyActivityChart(hourlyData) {
    if (!hourlyData || hourlyData.length === 0) return;
    
    const ctx = document.getElementById('hourlyActivityChart').getContext('2d');
    
    // Extract hours and counts
    const hours = hourlyData.map(item => item.hour);
    const counts = hourlyData.map(item => item.count);
    
    createBarChart(ctx, hours, counts, 'Quantidade de E-mails', 'Atividade por Hora do Dia');
}

// Bubble chart for contact activity
function createContactBubbleChart(contactData) {
    if (!contactData || contactData.length === 0) {
        // Se não houver dados, mostre uma mensagem alternativa
        const container = document.getElementById('contactBubbleChart').parentNode;
        container.innerHTML = '<div class="text-center py-4 text-muted"><i class="fas fa-users fa-3x mb-3"></i><p>Dados insuficientes para gerar o gráfico de contatos.</p></div>';
        return;
    }
    
    // Verifica se temos dados suficientes para um gráfico de bolhas
    const hasEnoughData = contactData.some(item => item.sent > 0 && item.received > 0);
    
    if (!hasEnoughData) {
        // Se não tivermos dados de enviados e recebidos, mostre um gráfico de barras alternativo
        const ctx = document.getElementById('contactBubbleChart').getContext('2d');
        
        // Limitar a apenas 3 contatos para evitar gráfico muito comprido
        const maxContacts = 3;
        
        // Preparar dados para um gráfico de barras empilhadas
        const labels = contactData.slice(0, maxContacts).map(item => {
            // Truncar labels muito longos
            if (item.label.length > 15) {
                return item.label.substring(0, 12) + '...';
            }
            return item.label;
        });
        
        const sentData = contactData.slice(0, maxContacts).map(item => item.sent || 0);
        const receivedData = contactData.slice(0, maxContacts).map(item => item.received || 0);
        
        // Criar gráfico de barras empilhadas
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Enviados',
                        data: sentData,
                        backgroundColor: 'rgba(40, 167, 69, 0.7)',
                        borderColor: 'rgba(40, 167, 69, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Recebidos',
                        data: receivedData,
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true, // Forçar proporção de aspecto para evitar alongamento
                aspectRatio: 1.5, // Proporção de largura/altura, ajuste conforme necessário
                plugins: {
                    legend: {
                        position: 'top', // Mover legenda para cima para economizar espaço vertical
                        labels: {
                            boxWidth: 12,
                            padding: 10
                        }
                    },
                    tooltip: {
                        callbacks: {
                            title: function(tooltipItems) {
                                // Mostra o contato completo no tooltip
                                const index = tooltipItems[0].dataIndex;
                                return contactData[index].label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        stacked: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
        
        return;
    }
    
    const ctx = document.getElementById('contactBubbleChart').getContext('2d');
    
    // Create bubble chart with contact data but limit the number and set aspect ratio
    const maxBubbles = 8; // Limitar para não ficar muito grande
    const limitedData = contactData.slice(0, maxBubbles);
    
    createBubbleChart(ctx, limitedData, 'Principais Contatos');
}

// Word cloud for email subjects
function createWordCloudVisualization(wordCloudData) {
    if (!wordCloudData || wordCloudData.length === 0) {
        // Se não houver dados, mostre uma mensagem alternativa
        const container = document.getElementById('subjectWordCloudContainer');
        container.innerHTML = '<div class="text-center py-4 text-muted"><i class="fas fa-font fa-3x mb-3"></i><p>Dados insuficientes para gerar a nuvem de palavras.</p></div>';
        return;
    }
    
    const container = document.getElementById('subjectWordCloudContainer');
    
    // Clear previous content
    container.innerHTML = '';
    
    // Limit to a reasonable number of words for better display
    const displayWords = wordCloudData.slice(0, Math.min(20, wordCloudData.length));
    
    // Create a wrapper with flex layout for better word distribution
    const wordCloudWrapper = document.createElement('div');
    wordCloudWrapper.id = 'wordCloudWrapper';
    wordCloudWrapper.style.width = '100%';
    wordCloudWrapper.style.minHeight = '280px';
    wordCloudWrapper.style.display = 'flex';
    wordCloudWrapper.style.flexWrap = 'wrap';
    wordCloudWrapper.style.justifyContent = 'center';
    wordCloudWrapper.style.alignItems = 'center';
    wordCloudWrapper.style.alignContent = 'center';
    wordCloudWrapper.style.gap = '10px';
    wordCloudWrapper.style.padding = '20px';
    container.appendChild(wordCloudWrapper);
    
    // Generate predefined colors for better visual appearance
    const colors = [
        '#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', 
        '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#06b6d4'
    ];
    
    // Get max weight for scaling
    const maxWeight = displayWords[0].weight;
    
    // Generate HTML for word cloud
    displayWords.forEach((item, index) => {
        // Scale font size based on word weight (frequency)
        const fontSizeMin = 14;
        const fontSizeMax = 40;
        const weightRatio = item.weight / maxWeight;
        const fontSize = fontSizeMin + ((fontSizeMax - fontSizeMin) * weightRatio);
        
        // Create span for word
        const span = document.createElement('span');
        span.textContent = item.text;
        span.className = 'word-cloud-item';
        span.style.fontSize = `${fontSize}px`;
        span.style.fontWeight = (weightRatio > 0.6) ? 'bold' : 'normal';
        span.style.color = colors[index % colors.length];
        span.style.padding = '8px';
        span.style.transition = 'all 0.3s ease';
        span.style.cursor = 'pointer';
        span.style.userSelect = 'none';
        span.style.textShadow = '0 1px 2px rgba(0,0,0,0.1)';
        span.setAttribute('title', `${item.text}: ${item.weight} ocorrências`);
        
        // Add hover effect
        span.addEventListener('mouseover', () => {
            span.style.transform = 'scale(1.2)';
            span.style.textShadow = '0 2px 8px rgba(0,0,0,0.2)';
            span.style.zIndex = '10';
        });
        span.addEventListener('mouseout', () => {
            span.style.transform = 'scale(1)';
            span.style.textShadow = '0 1px 2px rgba(0,0,0,0.1)';
            span.style.zIndex = '1';
        });
        
        // Add to container
        wordCloudWrapper.appendChild(span);
    });
    
    // Add info text
    const infoText = document.createElement('div');
    infoText.className = 'text-center mt-2';
    infoText.innerHTML = '<small class="text-muted">Termos mais frequentes nos assuntos de e-mail</small>';
    container.appendChild(infoText);
}

// Radar chart for email metrics
function createEmailMetricsRadarChart(metricsData) {
    if (!metricsData || !metricsData.labels || !metricsData.datasets) {
        // Se não houver dados adequados, mostre uma mensagem alternativa
        const container = document.getElementById('emailMetricsChart').parentNode;
        container.innerHTML = '<div class="text-center py-4 text-muted"><i class="fas fa-chart-pie fa-3x mb-3"></i><p>Dados insuficientes para gerar o gráfico de métricas.</p></div>';
        return;
    }
    
    const ctx = document.getElementById('emailMetricsChart').getContext('2d');
    
    // Create radar chart with metrics data
    createRadarChart(ctx, metricsData.labels, metricsData.datasets);
}

// Heat map for email activity by day/hour
function createActivityHeatmap(heatmapData) {
    if (!heatmapData || heatmapData.length === 0) {
        // Se não houver dados, mostre uma mensagem alternativa
        const container = document.getElementById('activityHeatmapChart').parentNode;
        container.innerHTML = '<div class="text-center py-4 text-muted"><i class="fas fa-chart-area fa-3x mb-3"></i><p>Dados insuficientes para gerar o mapa de calor.</p></div>';
        return;
    }
    
    // Transformar os dados para um formato mais simples quando não há dados suficientes
    // Se houver menos de 10 registros com atividade, use uma representação simplificada
    const hasData = heatmapData.some(value => value > 0);
    
    if (!hasData) {
        // Se não tiver dados, mostre uma mensagem
        const container = document.getElementById('activityHeatmapChart').parentNode;
        const message = document.createElement('div');
        message.className = 'text-center py-4 text-muted';
        message.innerHTML = '<i class="fas fa-chart-area fa-3x mb-3"></i><p>Dados insuficientes para gerar o mapa de calor.</p>';
        
        container.innerHTML = '';
        container.appendChild(message);
        return;
    }
    
    const ctx = document.getElementById('activityHeatmapChart').getContext('2d');
    
    // Create heat map chart with activity data
    createHeatMapChart(ctx, heatmapData);
}

// Demo data generators - used only when real data is unavailable
// IMPORTANT: These functions will be replaced by actual data from the API
// DO NOT use for production, only for development/visualization setup
function generateDemoHourlyData() {
    const hours = [];
    const data = [];
    
    for (let i = 0; i < 24; i++) {
        // Format hour as '00:00' string
        const hourStr = `${i.toString().padStart(2, '0')}:00`;
        // Generate random count between 0 and 15
        const count = Math.floor(Math.random() * 15);
        
        hours.push(hourStr);
        data.push({ hour: hourStr, count: count });
    }
    
    return data;
}

function generateDemoContactData() {
    const contacts = [
        { label: 'contato@empresa.com', sent: 15, received: 32 },
        { label: 'suporte@servico.com', sent: 8, received: 17 },
        { label: 'cliente@dominio.com.br', sent: 22, received: 11 },
        { label: 'vendas@loja.com', sent: 5, received: 28 },
        { label: 'marketing@newsletter.com', sent: 0, received: 43 }
    ];
    
    return contacts;
}

function generateDemoWordCloudData() {
    const words = [
        { text: 'reunião', weight: 35 },
        { text: 'relatório', weight: 28 },
        { text: 'orçamento', weight: 26 },
        { text: 'proposta', weight: 22 },
        { text: 'cliente', weight: 20 },
        { text: 'projeto', weight: 18 },
        { text: 'entrega', weight: 15 },
        { text: 'análise', weight: 12 },
        { text: 'feedback', weight: 10 },
        { text: 'urgente', weight: 8 },
        { text: 'confirmação', weight: 7 },
        { text: 'informações', weight: 6 },
        { text: 'contrato', weight: 5 },
        { text: 'apresentação', weight: 4 }
    ];
    
    return words;
}

function generateDemoMetricsData() {
    return {
        labels: [
            'Taxa de Resposta', 
            'Tempo de Resposta', 
            'Comprimento Médio', 
            'Uso de Anexos', 
            'Completude dos Dados',
            'Conversão'
        ],
        datasets: [
            {
                label: 'E-mails Enviados',
                data: [85, 65, 70, 40, 90, 75],
            },
            {
                label: 'E-mails Recebidos',
                data: [70, 80, 60, 50, 65, 60],
            }
        ]
    };
}

function generateDemoHeatmapData() {
    // Create an array for 7 days x 24 hours (168 cells)
    const data = new Array(168).fill(0);
    
    // Fill with random data - simulating real activity patterns
    const workdayHours = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18];
    const weekdays = [1, 2, 3, 4, 5]; // Monday to Friday
    
    // Higher activity during work hours on weekdays
    for (const day of weekdays) {
        for (const hour of workdayHours) {
            const index = day * 24 + hour;
            data[index] = Math.floor(Math.random() * 15) + 5; // 5-20 range for work hours
        }
    }
    
    // Lower activity at other times
    for (let i = 0; i < data.length; i++) {
        if (data[i] === 0) {
            data[i] = Math.floor(Math.random() * 5); // 0-4 range for non-work hours
        }
    }
    
    return data;
}