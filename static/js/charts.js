/**
 * charts.js - Biblioteca de funções para gráficos do sistema de análise de e-mails
 * 
 * Este arquivo contém funções comuns utilizadas pelos gráficos básicos e avançados 
 * do sistema. Ele deve ser incluído antes do advanced-charts.js.
 */

// Funções de utilidade para formatação
function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1.')
}

// Configurações padrão para os gráficos
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
        duration: 1000,
        easing: 'easeOutQuart'
    },
    plugins: {
        legend: {
            position: 'top',
            labels: {
                padding: 20,
                boxWidth: 12,
                usePointStyle: true
            }
        },
        tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            padding: 10,
            cornerRadius: 3,
            titleFont: {
                size: 13
            },
            bodyFont: {
                size: 12
            }
        }
    }
}

// Cores padronizadas para gráficos
const chartColors = {
    primary: 'rgba(54, 162, 235, 0.7)',
    secondary: 'rgba(255, 99, 132, 0.7)',
    success: 'rgba(75, 192, 192, 0.7)',
    warning: 'rgba(255, 159, 64, 0.7)',
    danger: 'rgba(255, 99, 132, 0.7)',
    info: 'rgba(54, 162, 235, 0.7)',
    light: 'rgba(220, 220, 220, 0.7)',
    dark: 'rgba(47, 79, 79, 0.7)',
    primaryBorder: 'rgba(54, 162, 235, 1)',
    secondaryBorder: 'rgba(255, 99, 132, 1)',
    successBorder: 'rgba(75, 192, 192, 1)',
    warningBorder: 'rgba(255, 159, 64, 1)',
    dangerBorder: 'rgba(255, 99, 132, 1)',
    infoBorder: 'rgba(54, 162, 235, 1)',
    lightBorder: 'rgba(220, 220, 220, 1)',
    darkBorder: 'rgba(47, 79, 79, 1)'
}

// Paleta multicores para gráficos com múltiplas séries
const colorPalette = [
    'rgba(54, 162, 235, 0.7)',
    'rgba(255, 99, 132, 0.7)',
    'rgba(75, 192, 192, 0.7)',
    'rgba(255, 159, 64, 0.7)',
    'rgba(153, 102, 255, 0.7)',
    'rgba(255, 205, 86, 0.7)',
    'rgba(201, 203, 207, 0.7)',
    'rgba(47, 79, 79, 0.7)'
]

const borderPalette = [
    'rgba(54, 162, 235, 1)',
    'rgba(255, 99, 132, 1)',
    'rgba(75, 192, 192, 1)',
    'rgba(255, 159, 64, 1)',
    'rgba(153, 102, 255, 1)',
    'rgba(255, 205, 86, 1)',
    'rgba(201, 203, 207, 1)',
    'rgba(47, 79, 79, 1)'
]

// Funções para criação de gráficos básicos

// Gráfico de barras simples
function createBarChart(ctx, labels, data, datasetLabel, title, options = {}) {
    const defaultOptions = {
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                },
                ticks: {
                    precision: 0
                }
            },
            x: {
                grid: {
                    display: false
                }
            }
        },
        plugins: {
            ...chartDefaults.plugins,
            title: {
                display: !!title,
                text: title || '',
                font: {
                    size: 16,
                    weight: 'bold'
                },
                padding: {
                    bottom: 20
                }
            }
        }
    }
    
    const mergedOptions = {...chartDefaults, ...defaultOptions, ...options}
    
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: datasetLabel,
                data: data,
                backgroundColor: chartColors.primary,
                borderColor: chartColors.primaryBorder,
                borderWidth: 1
            }]
        },
        options: mergedOptions
    })
}

// Gráfico de linha simples
function createLineChart(ctx, labels, data, datasetLabel, title, options = {}) {
    const defaultOptions = {
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                }
            },
            x: {
                grid: {
                    display: false
                }
            }
        },
        plugins: {
            ...chartDefaults.plugins,
            title: {
                display: !!title,
                text: title || '',
                font: {
                    size: 16,
                    weight: 'bold'
                },
                padding: {
                    bottom: 20
                }
            }
        }
    }
    
    const mergedOptions = {...chartDefaults, ...defaultOptions, ...options}
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: datasetLabel,
                data: data,
                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 2,
                tension: 0.3,
                fill: true,
                pointBackgroundColor: 'rgba(54, 162, 235, 1)',
                pointRadius: 3
            }]
        },
        options: mergedOptions
    })
}

// Gráfico de pizza simples
function createPieChart(ctx, labels, data, title, options = {}) {
    const defaultOptions = {
        plugins: {
            ...chartDefaults.plugins,
            title: {
                display: !!title,
                text: title || '',
                font: {
                    size: 16,
                    weight: 'bold'
                },
                padding: {
                    bottom: 20
                }
            }
        }
    }
    
    const mergedOptions = {...chartDefaults, ...defaultOptions, ...options}
    
    // Gerar cores para cada fatia do gráfico
    const backgroundColors = colorPalette.slice(0, labels.length);
    const borderColors = borderPalette.slice(0, labels.length);
    
    return new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: mergedOptions
    })
}

// Gráfico de rosca
function createDoughnutChart(ctx, labels, data, title, options = {}) {
    const defaultOptions = {
        cutout: '60%',
        plugins: {
            ...chartDefaults.plugins,
            title: {
                display: !!title,
                text: title || '',
                font: {
                    size: 16,
                    weight: 'bold'
                },
                padding: {
                    bottom: 20
                }
            }
        }
    }
    
    const mergedOptions = {...chartDefaults, ...defaultOptions, ...options}
    
    // Gerar cores para cada fatia do gráfico
    const backgroundColors = colorPalette.slice(0, labels.length);
    const borderColors = borderPalette.slice(0, labels.length);
    
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: mergedOptions
    })
}

// Funções para gráficos avançados

// Gráfico de bolhas (contatos)
function createBubbleChart(ctx, data, title, options = {}) {
    // Limitar o número de contatos para evitar sobrecarga visual
    const maxContacts = 5;
    const limitedData = data.slice(0, maxContacts);
    
    // Processar dados para formato de bolha (x, y, r)
    const bubbleData = limitedData.map(item => ({
        x: item.sent || 0,
        y: item.received || 0,
        r: Math.max(5, Math.min(15, Math.sqrt((item.sent || 0) + (item.received || 0)) * 1.5)), // Reduzido o tamanho máximo
        label: item.label || ''
    }));
    
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 1.3, // Proporção de largura/altura para evitar alongamento
        scales: {
            x: {
                title: {
                    display: true,
                    text: 'Enviados',
                    font: {
                        weight: 'bold',
                        size: 11 // Fonte menor
                    }
                },
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                },
                beginAtZero: true
            },
            y: {
                title: {
                    display: true,
                    text: 'Recebidos',
                    font: {
                        weight: 'bold',
                        size: 11 // Fonte menor
                    }
                },
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                },
                beginAtZero: true
            }
        },
        plugins: {
            ...chartDefaults.plugins,
            legend: {
                display: false // Remover legenda para economizar espaço
            },
            tooltip: {
                callbacks: {
                    title: function(context) {
                        return limitedData[context[0].dataIndex].label;
                    },
                    label: function(context) {
                        const item = limitedData[context.dataIndex];
                        return [
                            'Enviados: ' + (item.sent || 0),
                            'Recebidos: ' + (item.received || 0)
                        ];
                    }
                }
            },
            title: {
                display: false // Título removido para economizar espaço
            }
        }
    }
    
    const mergedOptions = {...chartDefaults, ...defaultOptions, ...options}
    
    return new Chart(ctx, {
        type: 'bubble',
        data: {
            datasets: [{
                label: 'Contatos',
                data: bubbleData,
                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: mergedOptions
    })
}

// Gráfico de radar (métricas)
function createRadarChart(ctx, labels, datasets, title, options = {}) {
    // Preparar cores para cada conjunto de dados
    const processedDatasets = datasets.map((dataset, index) => ({
        ...dataset,
        backgroundColor: `rgba(${index === 0 ? '54, 162, 235' : '255, 99, 132'}, 0.2)`,
        borderColor: `rgba(${index === 0 ? '54, 162, 235' : '255, 99, 132'}, 1)`,
        borderWidth: 2,
        pointBackgroundColor: `rgba(${index === 0 ? '54, 162, 235' : '255, 99, 132'}, 1)`,
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: `rgba(${index === 0 ? '54, 162, 235' : '255, 99, 132'}, 1)`,
        pointRadius: 4
    }));
    
    const defaultOptions = {
        scales: {
            r: {
                angleLines: {
                    display: true,
                    color: 'rgba(0, 0, 0, 0.1)'
                },
                suggestedMin: 0,
                suggestedMax: 100,
                ticks: {
                    backdropColor: 'rgba(255, 255, 255, 0.5)',
                    backdropPadding: 2,
                    showLabelBackdrop: true,
                    stepSize: 20
                },
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                },
                pointLabels: {
                    font: {
                        size: 11
                    }
                }
            }
        },
        plugins: {
            ...chartDefaults.plugins,
            title: {
                display: !!title,
                text: title || '',
                font: {
                    size: 16,
                    weight: 'bold'
                },
                padding: {
                    bottom: 20
                }
            }
        }
    }
    
    const mergedOptions = {...chartDefaults, ...defaultOptions, ...options}
    
    return new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: processedDatasets
        },
        options: mergedOptions
    })
}

// Gráfico de mapa de calor (atividade por dia/hora)
function createHeatMapChart(ctx, data, title, options = {}) {
    // Configuração para o mapa de calor
    const days = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
    const hours = Array.from({length: 24}, (_, i) => `${i}h`);
    
    // Transformar array unidimensional em matriz 7x24 para o mapa de calor
    const heatmapData = [];
    for (let d = 0; d < 7; d++) {
        const dayData = [];
        for (let h = 0; h < 24; h++) {
            dayData.push(data[d * 24 + h] || 0);
        }
        heatmapData.push(dayData);
    }
    
    // Encontrar o valor máximo para coloração
    const maxValue = Math.max(...data);
    
    // Criar datasets para cada dia da semana
    const datasets = days.map((day, index) => ({
        label: day,
        data: heatmapData[index],
        backgroundColor: function(context) {
            const value = context.dataset.data[context.dataIndex];
            if (value === 0) return 'rgba(240, 240, 240, 0.5)';
            const intensity = Math.min(1, value / (maxValue * 0.7));
            
            // Gradiente de cores: azul (baixo) -> amarelo (médio) -> vermelho (alto)
            if (intensity < 0.5) {
                // Azul para amarelo
                const g = Math.floor(162 + (255 - 162) * (intensity * 2));
                return `rgba(54, ${g}, ${Math.floor(235 - intensity * 2 * 235)}, 0.7)`;
            } else {
                // Amarelo para vermelho
                const r = Math.floor(255);
                const g = Math.floor(255 - (255 - 99) * ((intensity - 0.5) * 2));
                return `rgba(${r}, ${g}, 64, 0.7)`;
            }
        },
        borderColor: 'rgba(255, 255, 255, 0.3)',
        borderWidth: 1,
        borderRadius: 2,
        barPercentage: 0.95,
        categoryPercentage: 0.95
    }));
    
    const defaultOptions = {
        scales: {
            y: {
                stacked: true,
                ticks: {
                    display: true
                },
                grid: {
                    display: false
                }
            },
            x: {
                stacked: true,
                ticks: {
                    maxRotation: 0,
                    autoSkip: true,
                    callback: function(value, index) {
                        return hours[index];
                    }
                },
                grid: {
                    display: false
                }
            }
        },
        plugins: {
            ...chartDefaults.plugins,
            title: {
                display: !!title,
                text: title || '',
                font: {
                    size: 16,
                    weight: 'bold'
                },
                padding: {
                    bottom: 20
                }
            },
            tooltip: {
                callbacks: {
                    title: function(context) {
                        const dayIndex = context[0].datasetIndex;
                        const hourIndex = context[0].dataIndex;
                        return `${days[dayIndex]} às ${hours[hourIndex]}`;
                    },
                    label: function(context) {
                        const value = context.raw;
                        return value === 1 ? '1 email' : `${value} emails`;
                    }
                }
            }
        },
        responsive: true,
        maintainAspectRatio: false
    }
    
    const mergedOptions = {...chartDefaults, ...defaultOptions, ...options}
    
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hours,
            datasets: datasets
        },
        options: mergedOptions
    })
}