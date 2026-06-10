/* CodeMirror mode for the Plain language. */
(function () {
  if (typeof CodeMirror === "undefined") return;

  var CONTROL = new Set(("if then otherwise end repeat times while forever for each every other " +
    "going backwards stop skip give back try exit to call with expect").split(" "));
  var OPS = new Set(("plus minus multiplied divided by is not equal greater less than at least most " +
    "between and or one of in contains starts ends has does contain have start divisible odd even " +
    "positive negative empty squared").split(" "));
  var BUILTINS = new Set(("set put into add subtract from remove insert swap sort reverse print say ask " +
    "wait seconds read lines save count length sum average biggest smallest bigger smaller first last " +
    "the ones only where it uppercase lowercase letters keys values value split join random square root " +
    "absolute round floor middle remainder position item items list lookup being numbers grid filled " +
    "replace trim now arguments error pair true false").split(" "));

  CodeMirror.defineMode("plain-lang", function () {
    return {
      token: function (stream) {
        if (stream.match(/^#.*/)) return "comment";
        if (stream.match(/^"/)) {
          while (!stream.eol()) {
            if (stream.match(/^\[\w+\]/)) return "string"; // keep it simple: same color
            var ch = stream.next();
            if (ch === '"') break;
          }
          return "string";
        }
        if (stream.match(/^\d+(\.\d+)?/)) return "number";
        if (stream.match(/^(==|!=|<=|>=|\+=|-=|\*=|\/=|\/\/|[-+*/%^=<>\[\]{}(),:])/)) return "operator";
        if (stream.match(/^[A-Za-z_]\w*/)) {
          var w = stream.current().toLowerCase();
          if (CONTROL.has(w)) return "keyword";
          if (OPS.has(w)) return "atom";
          if (BUILTINS.has(w)) return "builtin";
          return "variable";
        }
        stream.next();
        return null;
      },
    };
  });
  CodeMirror.defineMIME("text/x-plain-lang", "plain-lang");
})();
