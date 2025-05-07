/**
 * main.js - Main JavaScript file for Inventory Management System
 */

// Configuração de Performance Otimizada
const PERFORMANCE_CONFIG = {
    // Indica se a animação pesada deve ser ativada (desative para melhor performance)
    enableHeavyAnimations: false,
    // Limita o número de itens em gráficos e visualizações
    maxChartItems: 5,
    // Define tempo de debounce para eventos que ocorrem frequentemente
    debounceTime: 150,
    // Ativa lazy-loading para imagens e elementos não visíveis
    enableLazyLoading: true,
    // Tamanho do lote para operações em massa (para evitar bloqueio de UI)
    batchSize: 50,
    // Tempo de atraso antes de iniciar carregamentos não críticos
    deferredLoadingDelay: 500,
};

// Função de debounce para limitar operações frequentes
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Carregamento progressivo e otimizado
document.addEventListener('DOMContentLoaded', function() {
    // Aplica animação de entrada somente se não estiver em modo de performance
    const contentWrapper = document.querySelector('.content-wrapper');
    if (contentWrapper) {
        if (PERFORMANCE_CONFIG.enableHeavyAnimations) {
            contentWrapper.classList.add('page-transition-in');
            
            // Remove a classe após a animação terminar
            setTimeout(() => {
                contentWrapper.classList.remove('page-transition-in');
            }, 300); // Reduzido de 500ms para 300ms para melhor performance
        } else {
            // Animação simplificada para dispositivos de baixo desempenho
            contentWrapper.style.opacity = '0';
            contentWrapper.style.display = 'block';
            setTimeout(() => {
                contentWrapper.style.transition = 'opacity 0.2s ease';
                contentWrapper.style.opacity = '1';
            }, 50);
        }
    }
    
    // Inicializa tooltips com lazy loading
    const initTooltips = () => {
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        if (tooltipTriggerList.length > 0) {
            const tooltipList = [...tooltipTriggerList].map(
                tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl, {
                    delay: { show: 500, hide: 100 } // Reduz chamadas desnecessárias
                })
            );
        }
    };
    
    // Atrasa inicialização de tooltips para priorizar carregamento do conteúdo
    setTimeout(initTooltips, PERFORMANCE_CONFIG.deferredLoadingDelay);
    
    // Sidebar toggle com transições otimizadas
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const wrapper = document.querySelector('.wrapper');
    
    // Sistema otimizado de pré-carregamento de imagens
    const preloadProfileImages = () => {
        const profileImages = document.querySelectorAll('.profile-image');
        profileImages.forEach(img => {
            if (img.getAttribute('src')) {
                const preloadLink = document.createElement('link');
                preloadLink.href = img.getAttribute('src');
                preloadLink.rel = 'preload';
                preloadLink.as = 'image';
                document.head.appendChild(preloadLink);
            }
        });
    };
    
    // Call preload immediately
    preloadProfileImages();
    
    if (sidebarToggle && sidebar) {
        // Check for stored sidebar state
        const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        
        // Apply stored state on load
        if (sidebarCollapsed) {
            wrapper.classList.add('sidebar-collapsed');
        }
        
        // Add transition class after a small delay to avoid initial animation
        setTimeout(() => {
            sidebar.classList.add('transition-ready');
        }, 100);
        
        sidebarToggle.addEventListener('click', function() {
            wrapper.classList.toggle('sidebar-collapsed');
            // Store state in localStorage
            localStorage.setItem('sidebarCollapsed', wrapper.classList.contains('sidebar-collapsed'));
        });
        
        // Handle responsive behavior with improved performance
        function handleResponsiveLayout() {
            if (window.innerWidth < 992) {
                wrapper.classList.add('sidebar-collapsed');
            } else if (localStorage.getItem('sidebarCollapsed') !== 'true') {
                wrapper.classList.remove('sidebar-collapsed');
            }
        }
        
        // Initialize responsive layout
        handleResponsiveLayout();
        
        // Add resize listener with debounce for better performance
        let resizeTimer;
        window.addEventListener('resize', function() {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(handleResponsiveLayout, 100);
        });
        
        // Enhanced sidebar links with advanced animations and active state detection
        const sidebarLinks = document.querySelectorAll('.sidebar-link');
        const currentPath = window.location.pathname;
        let lastActiveLink = null;

        // Add custom content transitions between pages
        const contentWrapper = document.querySelector('.content-wrapper');
        
        // Add visual feedback and sound effect on link click
        sidebarLinks.forEach(link => {
            // Enhance links with ripple effect
            link.addEventListener('mousedown', function(e) {
                const ripple = document.createElement('div');
                ripple.className = 'ripple';
                this.appendChild(ripple);
                
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                
                ripple.style.width = ripple.style.height = `${size}px`;
                ripple.style.left = `${e.clientX - rect.left - size/2}px`;
                ripple.style.top = `${e.clientY - rect.top - size/2}px`;
                
                // Remove ripple after animation completes
                setTimeout(() => {
                    ripple.remove();
                }, 600);
            });
            
            // Add click handler with page transition effects
            link.addEventListener('click', function(e) {
                if (this.href === window.location.href) {
                    e.preventDefault();
                    return;
                }
                
                if (window.innerWidth < 992) {
                    wrapper.classList.add('sidebar-collapsed');
                    localStorage.setItem('sidebarCollapsed', 'true');
                }
                
                // Set this link as active for other links to reference
                lastActiveLink = this;
                
                // Add page transition effect with seamless navigation
                const targetUrl = this.getAttribute('href');
                
                // Don't transition if already on this page
                if (targetUrl === window.location.pathname) {
                    return;
                }
                
                // Prevent default link navigation so we can do animation first
                e.preventDefault();
                
                // Add exit animation 
                contentWrapper.classList.add('page-transition-out');
                
                // After animation completes, navigate to the new page
                setTimeout(() => {
                    window.location.href = targetUrl;
                }, 300);
                
                // Mark all other links as inactive
                sidebarLinks.forEach(otherLink => {
                    if (otherLink !== this) {
                        otherLink.classList.remove('active');
                    }
                });
                
                // Add active class to current link
                this.classList.add('active');
                
                // Fancy visual effect for menu links when clicked
                sidebarLinks.forEach(otherLink => {
                    if (otherLink !== this) {
                        otherLink.style.opacity = '0.6';
                        otherLink.style.transform = 'scale(0.95)';
                        setTimeout(() => {
                            otherLink.style.opacity = '';
                            otherLink.style.transform = '';
                        }, 500);
                    } else {
                        this.style.transform = 'scale(1.05)';
                        setTimeout(() => {
                            this.style.transform = '';
                        }, 300);
                    }
                });
            });
        });
    }
    
    // Make table rows with data-bs-toggle="collapse" clickable
    const clickableRows = document.querySelectorAll('tr.clickable');
    clickableRows.forEach(row => {
        row.addEventListener('click', function() {
            const target = this.getAttribute('data-bs-target');
            const element = document.querySelector(target);
            const bsCollapse = new bootstrap.Collapse(element, {
                toggle: true
            });
        });
    });
    
    // Handle date range validation in report form
    const startDateInput = document.getElementById('date_range_start');
    const endDateInput = document.getElementById('date_range_end');
    
    if (startDateInput && endDateInput) {
        endDateInput.addEventListener('change', function() {
            if (startDateInput.value && endDateInput.value) {
                if (new Date(endDateInput.value) < new Date(startDateInput.value)) {
                    alert('End date must be after start date');
                    endDateInput.value = '';
                }
            }
        });
        
        startDateInput.addEventListener('change', function() {
            if (startDateInput.value && endDateInput.value) {
                if (new Date(endDateInput.value) < new Date(startDateInput.value)) {
                    alert('Start date must be before end date');
                    startDateInput.value = '';
                }
            }
        });
    }
    
    // Prevent both include_sent and include_received from being unchecked
    const includeSentCheckbox = document.getElementById('include_sent');
    const includeReceivedCheckbox = document.getElementById('include_received');
    
    if (includeSentCheckbox && includeReceivedCheckbox) {
        includeSentCheckbox.addEventListener('change', function() {
            if (!this.checked && !includeReceivedCheckbox.checked) {
                includeReceivedCheckbox.checked = true;
                alert('At least one email type must be selected');
            }
        });
        
        includeReceivedCheckbox.addEventListener('change', function() {
            if (!this.checked && !includeSentCheckbox.checked) {
                includeSentCheckbox.checked = true;
                alert('At least one email type must be selected');
            }
        });
    }
    
    // Add animation for cards on the dashboard
    const animateCards = document.querySelectorAll('.animate-card');
    if (animateCards.length > 0) {
        const animateCardObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate__animated', 'animate__fadeInUp');
                    animateCardObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        
        animateCards.forEach(card => {
            animateCardObserver.observe(card);
        });
    }
    
    // Dark Mode toggle
    const darkModeSwitch = document.getElementById('darkModeSwitch');
    const htmlElement = document.documentElement;
    
    if (darkModeSwitch) {
        // Check for stored dark mode preference
        const darkModeEnabled = localStorage.getItem('darkModeEnabled') === 'true';
        
        // Apply stored preference on load
        if (darkModeEnabled) {
            htmlElement.setAttribute('data-bs-theme', 'dark');
            darkModeSwitch.checked = true;
            document.body.classList.add('dark-mode');
        }
        
        // Toggle dark mode
        darkModeSwitch.addEventListener('change', function() {
            if (this.checked) {
                htmlElement.setAttribute('data-bs-theme', 'dark');
                document.body.classList.add('dark-mode');
                localStorage.setItem('darkModeEnabled', 'true');
            } else {
                htmlElement.setAttribute('data-bs-theme', 'light');
                document.body.classList.remove('dark-mode');
                localStorage.setItem('darkModeEnabled', 'false');
            }
        });
    }
});
