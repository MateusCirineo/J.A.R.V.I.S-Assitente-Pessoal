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
function buildOtlpResourceAttributes(config, sdkName, sdkVersion) {
    return {
        ...config.resourceAttributes,
        'service.name': config.serviceName || 'unknown_service',
        ...config.environment && {
            'deployment.environment': config.environment
        },
        ...config.serviceVersion && {
            'service.version': config.serviceVersion
        },
        'telemetry.sdk.name': sdkName,
        'telemetry.sdk.version': sdkVersion
    };
}
const OS_NAMES = {
    darwin: 'macOS',
    win32: 'Windows',
    linux: 'Linux',
    android: 'Android',
    freebsd: 'FreeBSD',
    openbsd: 'OpenBSD',
    sunos: 'SunOS',
    aix: 'AIX',
    'Mac OS X': 'macOS'
};
function normalizeOsName(name) {
    if (!name) return;
    return Object.prototype.hasOwnProperty.call(OS_NAMES, name) ? OS_NAMES[name] : name;
}
function osResourceAttributes(name, version) {
    const osName = normalizeOsName(name);
    return {
        ...osName ? {
            'os.name': osName
        } : {},
        ...version ? {
            'os.version': version
        } : {}
    };
}
__webpack_require__.d(__webpack_exports__, {
    buildOtlpResourceAttributes: ()=>buildOtlpResourceAttributes,
    normalizeOsName: ()=>normalizeOsName,
    osResourceAttributes: ()=>osResourceAttributes
});
exports.buildOtlpResourceAttributes = __webpack_exports__.buildOtlpResourceAttributes;
exports.normalizeOsName = __webpack_exports__.normalizeOsName;
exports.osResourceAttributes = __webpack_exports__.osResourceAttributes;
for(var __rspack_i in __webpack_exports__)if (-1 === [
    "buildOtlpResourceAttributes",
    "normalizeOsName",
    "osResourceAttributes"
].indexOf(__rspack_i)) exports[__rspack_i] = __webpack_exports__[__rspack_i];
Object.defineProperty(exports, '__esModule', {
    value: true
});
