// Remove only independent, read-only, error-only top-level guards from request slices.
// Functions and branches with mutations or unknown calls are retained unchanged.
function spProjectRequestGuards(statements) {
  function member(node, object, method) {
    return node?.type === "MemberExpression" && !node.computed &&
      node.object?.type === "Identifier" && node.object.name === object && node.property?.name === method;
  }
  function pure(node) {
    if (!node) return true;
    if (["Identifier", "Literal"].includes(node.type)) return true;
    if (node.type === "MemberExpression") return pure(node.object) && (!node.computed || pure(node.property));
    if (node.type === "UnaryExpression") return node.operator !== "delete" && pure(node.argument);
    if (["BinaryExpression", "LogicalExpression"].includes(node.type)) return pure(node.left) && pure(node.right);
    if (node.type === "ConditionalExpression") return pure(node.test) && pure(node.consequent) && pure(node.alternate);
    if (node.type === "ArrayExpression") return node.elements.every(pure);
    if (node.type === "CallExpression") {
      const callee=node.callee;
      const comparison=callee?.type==="MemberExpression" && !callee.computed && ["__eq","__ne","__gt","__ge","__lt","__le"].includes(callee.property?.name) && callee.object?.type==="MemberExpression" && !callee.object.computed && callee.object.property?.name==="math" && member(callee.object.object, "$", "pine");
      return (comparison || member(node.callee, "$", "get") || member(node.callee, "timeframe", "in_seconds") || member(node.callee, "timeframe", "param")) && node.arguments.every(pure);
    }
    return false;
  }
  function guard(node) {
    const names = new Set(); let errors = 0;
    function branch(stmt) {
      if (!stmt) return true;
      if (stmt.type === "BlockStatement") return stmt.body.every(branch);
      if (stmt.type === "IfStatement") return pure(stmt.test) && branch(stmt.consequent) && branch(stmt.alternate);
      if (stmt.type === "VariableDeclaration" && stmt.kind === "const") return stmt.declarations.every(decl => {
        const call = decl.init;
        if (decl.id?.type !== "Identifier" || call?.type !== "CallExpression" ||
            !(member(call.callee, "runtime", "param") || member(call.callee, "runtime", "error")) || !call.arguments.every(pure)) return false;
        if (member(call.callee, "runtime", "error")) errors++;
        names.add(decl.id.name); return true;
      });
      if (stmt.type === "ExpressionStatement") return stmt.expression?.type === "Identifier" && names.has(stmt.expression.name);
      return false;
    }
    return node.type === "IfStatement" && branch(node) && errors > 0;
  }
  return statements.filter(stmt => !guard(stmt));
}
