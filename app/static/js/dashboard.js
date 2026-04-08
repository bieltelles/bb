// Dashboard Charts - Chart.js
// Variables monthlyData and empenhoData are injected by the template

const brlFormatter = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
});

// Monthly Execution Bar Chart
(function() {
    const ctx = document.getElementById('monthlyChart');
    if (!ctx || !monthlyData || monthlyData.length === 0) {
        if (ctx) {
            ctx.parentElement.innerHTML = '<p class="text-muted text-center py-5">Nenhum dado de competencia cadastrado.</p>';
        }
        return;
    }

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: monthlyData.map(d => d.label),
            datasets: [
                {
                    label: 'Valor Total',
                    data: monthlyData.map(d => d.valor_total),
                    backgroundColor: 'rgba(13, 110, 253, 0.7)',
                    borderColor: 'rgba(13, 110, 253, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'IR Retido',
                    data: monthlyData.map(d => d.total_ir),
                    backgroundColor: 'rgba(255, 193, 7, 0.7)',
                    borderColor: 'rgba(255, 193, 7, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Valor Liquido',
                    data: monthlyData.map(d => d.total_liquido),
                    backgroundColor: 'rgba(25, 135, 84, 0.7)',
                    borderColor: 'rgba(25, 135, 84, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { usePointStyle: true, padding: 15, font: { size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + brlFormatter.format(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            if (value >= 1000) return 'R$ ' + (value / 1000).toFixed(0) + 'k';
                            return 'R$ ' + value.toFixed(0);
                        }
                    },
                    grid: { color: 'rgba(0,0,0,0.05)' }
                },
                x: {
                    grid: { display: false }
                }
            }
        }
    });
})();

// Empenho Execution Doughnut Chart
(function() {
    const ctx = document.getElementById('empenhoChart');
    if (!ctx || !empenhoData || empenhoData.length === 0) {
        if (ctx) {
            ctx.parentElement.innerHTML = '<p class="text-muted text-center py-5">Nenhum dado de empenho.</p>';
        }
        return;
    }

    const colors = [
        'rgba(13, 110, 253, 0.8)',   // Blue - SE 98
        'rgba(25, 135, 84, 0.8)',    // Green - SE 93
        'rgba(253, 126, 20, 0.8)'    // Orange - SE 92
    ];
    const borderColors = [
        'rgba(13, 110, 253, 1)',
        'rgba(25, 135, 84, 1)',
        'rgba(253, 126, 20, 1)'
    ];

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: empenhoData.map(d => d.label),
            datasets: [{
                data: empenhoData.map(d => d.executado),
                backgroundColor: colors.slice(0, empenhoData.length),
                borderColor: borderColors.slice(0, empenhoData.length),
                borderWidth: 2,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { usePointStyle: true, padding: 12, font: { size: 11 } }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = total > 0 ? ((context.parsed / total) * 100).toFixed(1) : 0;
                            return context.label + ': ' + brlFormatter.format(context.parsed) + ' (' + pct + '%)';
                        }
                    }
                }
            },
            cutout: '55%'
        }
    });
})();
