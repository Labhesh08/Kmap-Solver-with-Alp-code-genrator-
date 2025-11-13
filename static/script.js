function copyExpression() {
    const expr = document.getElementById("simplified_expr");
    expr.select();
    expr.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(expr.value)
        .then(() => {
            alert("Simplified Boolean expression copied!");
        })
        .catch(err => {
            alert("Failed to copy: " + err);
        });
}