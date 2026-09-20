"use strict";
var __webpack_require__ = {};
(()=>{
    __webpack_require__.d = (exports1, getters, values)=>{
        var define = (defs, kind)=>{
            for(var key in defs)if (__webpack_require__.o(defs, key) && !__webpack_require__.o(exports1, key)) Object.defineProperty(exports1, key, {
                enumerable: true,
                [kind]: defs[key]
            });
        };
        define(getters, "get");
        define(values, "value");
    };
})();
(()=>{
    __webpack_require__.o = (obj, prop)=>Object.prototype.hasOwnProperty.call(obj, prop);
})();
(()=>{
    __webpack_require__.r = (exports1)=>{
        if ("u" > typeof Symbol && Symbol.toStringTag) Object.defineProperty(exports1, Symbol.toStringTag, {
            value: 'Module'
        });
        Object.defineProperty(exports1, '__esModule', {
            value: true
        });
    };
})();
var __webpack_exports__ = {};
__webpack_require__.r(__webpack_exports__);
__webpack_require__.d(__webpack_exports__, {
    UNKNOWN_FUNCTION: ()=>UNKNOWN_FUNCTION,
    createFrame: ()=>createFrame
});
const index_js_namespaceObject = require("../../utils/index.js");
const UNKNOWN_FUNCTION = '?';
const MASKED_URL_PREFIX = 'webkit-masked-url://';
const ANONYMOUS_FILENAME = '<anonymous>';
function createFrame(platform, filename, func, lineno, colno) {
    const frame = {
        platform,
        filename,
        function: '<anonymous>' === func ? UNKNOWN_FUNCTION : func,
        in_app: !!filename && !filename.startsWith(MASKED_URL_PREFIX) && filename !== ANONYMOUS_FILENAME
    };
    if (!(0, index_js_namespaceObject.isUndefined)(lineno)) frame.lineno = lineno;
    if (!(0, index_js_namespaceObject.isUndefined)(colno)) frame.colno = colno;
    return frame;
}
exports.UNKNOWN_FUNCTION = __webpack_exports__.UNKNOWN_FUNCTION;
exports.createFrame = __webpack_exports__.createFrame;
for(var __rspack_i in __webpack_exports__)if (-1 === [
    "UNKNOWN_FUNCTION",
    "createFrame"
].indexOf(__rspack_i)) exports[__rspack_i] = __webpack_exports__[__rspack_i];
Object.defineProperty(exports, '__esModule', {
    value: true
});
