

# ---------- Flask Route ----------
@app.route("/", methods=["GET", "POST"])
def index():
    result = {}
    if request.method == "POST":
        mode = request.form.get("mode")

        if mode == "expr":
            expr_input = request.form.get("boolean_expr", "").strip()
            if not expr_input:
                result["error"] = "Please enter a Boolean expression."
                return render_template("index.html", result=result)
            try:
                clean = preprocess_expression(expr_input)
                used_vars = sorted(set(re.findall(r"[A-D]", clean)))
                local = {v: symbols(v) for v in ["A", "B", "C", "D"]}
                expr = sympify(clean, locals=local)
                simplified = simplify_logic(expr, form="dnf")

                vars_syms = [symbols(v) for v in used_vars]
                truth = []
                for vals in itertools.product([0, 1], repeat=len(vars_syms)):
                    subs = dict(zip(vars_syms, vals))
                    truth.append(list(vals) + [int(bool(expr.subs(subs)))])

                rows, cols, grid = generate_kmap(expr, used_vars)
                asm_code = generate_tasm_output(expr_input, str(simplified), truth, grid)

                result.update({
                    "mode": "expr",
                    "variables": used_vars,
                    "truth_table": truth,
                    "sop_expr": f"Y = {expr_input}",
                    "simplified": f"Y = {simplified}",
                    "kmap_rows": rows,
                    "kmap_cols": cols,
                    "kmap_grid": grid,
                    "asm_code": asm_code
                })
            except Exception as e:
                result["error"] = f"Error parsing input: {e}"

        elif mode == "kmap":
            var_count = int(request.form.get("var_count", 2))
            raw = request.form.get("kmap_values", "").strip()
            try:
                vals = [int(x) for x in re.findall(r"[01]", raw)]
                total = 2 ** var_count
                if len(vals) != total:
                    result["error"] = f"Expected {total} values for {var_count} variables."
                    return render_template("index.html", result=result)
                vars_ = ["A", "B", "C", "D"][:var_count]
                sop = kmap_to_sop(vals, vars_)
                local = {v: symbols(v) for v in vars_}
                expr = sympify(sop, locals=local)
                simplified = simplify_logic(expr, form="dnf")
                rows, cols, grid = generate_kmap(expr, vars_)

                truth = []
                for combo in itertools.product([0, 1], repeat=len(vars_)):
                    subs = dict(zip([symbols(v) for v in vars_], combo))
                    truth.append(list(combo) + [int(bool(expr.subs(subs)))])

                asm_code = generate_tasm_output(sop, str(simplified), truth, grid)

                result.update({
                    "mode": "kmap",
                    "variables": vars_,
                    "truth_table": truth,
                    "sop_expr": f"Y = {sop}",
                    "simplified": f"Y = {simplified}",
                    "kmap_rows": rows,
                    "kmap_cols": cols,
                    "kmap_grid": grid,
                    "asm_code": asm_code
                })
            except Exception as e:
                result["error"] = f"Error reading K-map: {e}"

    return render_template("index.html", result=result)


if __name__ == "__main__":
    app.run(debug=True)