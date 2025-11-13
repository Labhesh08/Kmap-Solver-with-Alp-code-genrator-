from flask import Flask, render_template, request
from sympy import symbols, simplify_logic, sympify
import itertools, re, textwrap

app = Flask(__name__)

# ---------- Preprocess Boolean Expression ----------
def preprocess_expression(expr):
    expr = expr.upper().strip()
    expr = re.sub(r"([A-Z])'", r"~\1", expr)
    expr = expr.replace("!", "~")
    expr = expr.replace("+", "|").replace("*", "&").replace(".", "&")
    expr = re.sub(r"(?<=[A-Z])(?=[A-Z])", "&", expr)
    expr = re.sub(r"(?<=[A-Z])(?=~[A-Z])", "&", expr)
    expr = re.sub(r"(?<=\))(?=[A-Z])", "&", expr)
    return expr


# ---------- Gray Code ----------
def gray_code(n):
    if n == 1:
        return ["0", "1"]
    prev = gray_code(n - 1)
    return ["0" + p for p in prev] + ["1" + p for p in reversed(prev)]


# ---------- Generate K-Map ----------
def generate_kmap(expr, variables):
    n = len(variables)
    if n == 2:
        row_bits = gray_code(1)
        col_bits = gray_code(1)
    elif n == 3:
        row_bits = gray_code(1)
        col_bits = gray_code(2)
    elif n == 4:
        row_bits = gray_code(2)
        col_bits = gray_code(2)
    else:
        raise ValueError("Only supports 2 to 4 variables.")

    grid = []
    for r in row_bits:
        row_vals = []
        for c in col_bits:
            bits = [int(x) for x in (r + c)]
            subs = {symbols(v): bits[i] for i, v in enumerate(variables)}
            row_vals.append(int(bool(expr.subs(subs))))
        grid.append(row_vals)
    return row_bits, col_bits, grid


# ---------- K-Map → SOP ----------
def kmap_to_sop(kmap_values, variables):
    n = len(variables)
    terms = []
    for i, val in enumerate(kmap_values):
        if val == 1:
            bits = list(map(int, f"{i:0{n}b}"))
            parts = [v if b else f"~{v}" for v, b in zip(variables, bits)]
            terms.append("(" + " & ".join(parts) + ")")
    return " | ".join(terms) if terms else "0"


# ---------- Generate Safe DB Line ----------
def make_db_line(label, content):
    """Safely wraps long strings into DB lines for TASM (avoids long-line errors)."""
    lines = textwrap.wrap(content, 80)
    db_lines = []
    for i, part in enumerate(lines):
        suffix = "," if i < len(lines) - 1 else ""
        db_lines.append(f"    {label}{i if i else ''} DB '{part}',13,10,'${suffix}")
    return "\n".join(db_lines)


# ---------- Generate Turbo Assembler Output ----------
def generate_tasm_output(sop_display, simplified_display, truth_table, kmap_grid):
    def esc(s): return s.replace("'", "''")

    sop_asm = esc(sop_display)
    simp_asm = esc(simplified_display)

    # truth table rows
    tt_lines = []
    for i, row in enumerate(truth_table):
        bits = " ".join(str(x) for x in row[:-1])
        y = row[-1]
        tt_lines.append(f"    ttLine{i+1} DB '{bits} | {y}',13,10,'$'")

    # kmap rows
    km_lines = []
    for i, r in enumerate(kmap_grid):
        row_str = " ".join(str(x) for x in r)
        km_lines.append(f"    kLine{i+1} DB '{row_str}',13,10,'$'")

    asm = [
        "TITLE Boolean Logic Display",
        ".MODEL SMALL",
        ".STACK 100H",
        "",
        "DATA SEGMENT",
        "    msg1     DB 'SOP Expression:',13,10,'$'",
        f"    sopExpr  DB 'Y = {sop_asm}',13,10,'$'",
        "    msg2     DB 'Simplified Boolean Expression:',13,10,'$'",
        f"    simpExpr DB 'Y = {simp_asm}',13,10,'$'",
        "    msg3     DB 'Truth Table:',13,10,'$'",
        "    msg4     DB '----------------',13,10,'$'",
    ] + tt_lines + [
        "    msg5     DB 'K-Map (commented below):',13,10,'$'",
    ] + km_lines + [
        "    msgEnd   DB 13,10,'$'",
        "DATA ENDS",
        "",
        "CODE SEGMENT",
        "ASSUME DS:DATA, CS:CODE",
        "MAIN PROC",
        "    MOV AX, DATA",
        "    MOV DS, AX",
        "",
        "    ; === Display SOP Expression ===",
        "    LEA DX, msg1",
        "    MOV AH, 9",
        "    INT 21H",
        "    LEA DX, sopExpr",
        "    MOV AH, 9",
        "    INT 21H",
        "",
        "    ; === Display Simplified Boolean Expression ===",
        "    LEA DX, msg2",
        "    MOV AH, 9",
        "    INT 21H",
        "    LEA DX, simpExpr",
        "    MOV AH, 9",
        "    INT 21H",
        "",
        "    ; === Display Truth Table ===",
        "    LEA DX, msg3",
        "    MOV AH, 9",
        "    INT 21H",
        "    LEA DX, msg4",
        "    MOV AH, 9",
        "    INT 21H",
    ]

    for i in range(len(tt_lines)):
        asm += [f"    LEA DX, ttLine{i+1}", "    MOV AH, 9", "    INT 21H"]

    asm += [
        "",
        "    ; === Display K-Map Section ===",
        "    LEA DX, msg5",
        "    MOV AH, 9",
        "    INT 21H",
    ]

    for i in range(len(km_lines)):
        asm += [f"    LEA DX, kLine{i+1}", "    MOV AH, 9", "    INT 21H"]

    asm += [
        "",
        "    LEA DX, msgEnd",
        "    MOV AH, 9",
        "    INT 21H",
        "",
        "    MOV AH, 4CH",
        "    MOV AL, 00H",
        "    INT 21H",
        "MAIN ENDP",
        "CODE ENDS",
        "END MAIN",
    ]
    return "\n".join(asm)


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