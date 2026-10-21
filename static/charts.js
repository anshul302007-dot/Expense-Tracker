
document.addEventListener("DOMContentLoaded", function () {

    const categoryElement = document.getElementById("categoryChart");
    const monthlyElement = document.getElementById("monthlyChart");

    if (!categoryElement || !monthlyElement) return;

    const categoryData = JSON.parse(
        document.getElementById("category-data").textContent
    );

    const monthlyData = JSON.parse(
        document.getElementById("monthly-data").textContent
    );

    const categoryColors = [
        "#667eea", "#f59e0b", "#10b981",
        "#ef4444", "#8b5cf6", "#06b6d4",
        "#ec4899", "#84cc16", "#64748b"
    ];

    if (categoryData.length > 0) {
        new Chart(categoryElement, {
            type: "doughnut",
            data: {
                labels: categoryData.map(item => item.name),
                datasets: [{
                    data: categoryData.map(item => item.amount),
                    backgroundColor: categoryColors,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: "bottom"
                    }
                }
            }
        });
    }

    new Chart(monthlyElement, {
        type: "bar",
        data: {
            labels: monthlyData.labels,
            datasets: [
                {
                    label: "Income",
                    data: monthlyData.income,
                    backgroundColor: "#10b981"
                },
                {
                    label: "Expenses",
                    data: monthlyData.expenses,
                    backgroundColor: "#ef4444"
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });

});
