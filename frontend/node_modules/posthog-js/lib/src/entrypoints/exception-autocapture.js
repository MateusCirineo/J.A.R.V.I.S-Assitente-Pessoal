"use strict";
var __read = (this && this.__read) || function (o, n) {
    var m = typeof Symbol === "function" && o[Symbol.iterator];
    if (!m) return o;
    var i = m.call(o), r, ar = [], e;
    try {
        while ((n === void 0 || n-- > 0) && !(r = i.next()).done) ar.push(r.value);
    }
    catch (error) { e = { error: error }; }
    finally {
        try {
            if (r && !r.done && (m = i["return"])) m.call(i);
        }
        finally { if (e) throw e.error; }
    }
    return ar;
};
var __spreadArray = (this && this.__spreadArray) || function (to, from, pack) {
    if (pack || arguments.length === 2) for (var i = 0, l = from.length, ar; i < l; i++) {
        if (ar || !(i in from)) {
            if (!ar) ar = Array.prototype.slice.call(from, 0, i);
            ar[i] = from[i];
        }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
};
Object.defineProperty(exports, "__esModule", { value: true });
var globals_1 = require("@posthog/browser-common/utils/globals");
var globals_2 = require("../utils/globals");
var logger_1 = require("@posthog/browser-common/utils/logger");
var core_1 = require("@posthog/core");
var posthog_exceptions_1 = require("../posthog-exceptions");
var logger = (0, logger_1.createLogger)('[ExceptionAutocapture]');
var errorPropertiesBuilder = (0, posthog_exceptions_1.buildErrorPropertiesBuilder)();
var safelyBuildAndCapture = function (captureFn, buildProperties) {
    try {
        captureFn(buildProperties());
    }
    catch (_a) {
        // Exception autocapture must never throw into customer code. Do not log here because
        // console.error may be instrumented and would re-enter exception autocapture.
    }
};
// `window.onerror` exposes the location positionally, so preserve it when there is no Error object.
var resolveOnErrorInput = function (_a) {
    var _b = __read(_a, 5), event = _b[0], source = _b[1], lineno = _b[2], colno = _b[3], error = _b[4];
    if (error != null) {
        return error;
    }
    if ((0, core_1.isString)(event) && (0, core_1.isString)(source) && source.length > 0 && typeof ErrorEvent !== 'undefined') {
        try {
            return new ErrorEvent('error', { message: event, filename: source, lineno: lineno, colno: colno });
        }
        catch (_c) {
            return event;
        }
    }
    return event;
};
var wrapOnError = function (captureFn) {
    var win = globals_1.window;
    if (!win) {
        logger.info('window not available, cannot wrap onerror');
    }
    var originalOnError = win.onerror;
    win.onerror = function () {
        var _a;
        var args = [];
        for (var _i = 0; _i < arguments.length; _i++) {
            args[_i] = arguments[_i];
        }
        safelyBuildAndCapture(captureFn, function () {
            return errorPropertiesBuilder.buildFromUnknown(resolveOnErrorInput(args), {
                mechanism: { handled: false },
            });
        });
        return (0, core_1.isFunction)(originalOnError) ? ((_a = originalOnError.apply(void 0, __spreadArray([], __read(args), false))) !== null && _a !== void 0 ? _a : false) : false;
    };
    win.onerror.__POSTHOG_INSTRUMENTED__ = true;
    return function () {
        var _a;
        (_a = win.onerror) === null || _a === void 0 ? true : delete _a.__POSTHOG_INSTRUMENTED__;
        win.onerror = originalOnError;
    };
};
var wrapUnhandledRejection = function (captureFn, defaultReturnValue) {
    if (defaultReturnValue === void 0) { defaultReturnValue = false; }
    var win = globals_1.window;
    if (!win) {
        logger.info('window not available, cannot wrap onUnhandledRejection');
    }
    var originalOnUnhandledRejection = win.onunhandledrejection;
    win.onunhandledrejection = function (ev) {
        var _a;
        safelyBuildAndCapture(captureFn, function () {
            return errorPropertiesBuilder.buildFromUnknown(ev, {
                mechanism: { handled: false },
            });
        });
        return (0, core_1.isFunction)(originalOnUnhandledRejection)
            ? ((_a = originalOnUnhandledRejection(ev)) !== null && _a !== void 0 ? _a : false)
            : defaultReturnValue;
    };
    win.onunhandledrejection.__POSTHOG_INSTRUMENTED__ = true;
    return function () {
        var _a;
        (_a = win.onunhandledrejection) === null || _a === void 0 ? true : delete _a.__POSTHOG_INSTRUMENTED__;
        win.onunhandledrejection = originalOnUnhandledRejection;
    };
};
var wrapConsoleError = function (captureFn) {
    var con = console;
    if (!con) {
        logger.info('console not available, cannot wrap console.error');
    }
    var originalConsoleError = con.error;
    con.error = function () {
        var args = [];
        for (var _i = 0; _i < arguments.length; _i++) {
            args[_i] = arguments[_i];
        }
        safelyBuildAndCapture(captureFn, function () {
            var event;
            if (args.length == 1) {
                event = args[0];
            }
            else {
                event = args.join(' ');
            }
            var error = args.find(function (arg) { return arg instanceof Error; });
            return errorPropertiesBuilder.buildFromUnknown(error || event, {
                mechanism: { handled: false },
                syntheticException: new Error('PostHog syntheticException'),
                skipFirstLines: 2,
            });
        });
        if ((0, core_1.isFunction)(originalConsoleError)) {
            originalConsoleError.apply(void 0, __spreadArray([], __read(args), false));
        }
    };
    con.error.__POSTHOG_INSTRUMENTED__ = true;
    return function () {
        var _a;
        (_a = con.error) === null || _a === void 0 ? true : delete _a.__POSTHOG_INSTRUMENTED__;
        con.error = originalConsoleError;
    };
};
var posthogErrorWrappingFunctions = {
    wrapOnError: wrapOnError,
    wrapUnhandledRejection: wrapUnhandledRejection,
    wrapConsoleError: wrapConsoleError,
};
globals_2.assignableWindow.__PosthogExtensions__ = globals_2.assignableWindow.__PosthogExtensions__ || {};
globals_2.assignableWindow.__PosthogExtensions__.errorWrappingFunctions = posthogErrorWrappingFunctions;
// we used to put these on window, and now we put them on __PosthogExtensions__
// but that means that old clients which lazily load this extension are looking in the wrong place
// yuck,
// so we also put them directly on the window
// when 1.161.1 is the oldest version seen in production we can remove this
globals_2.assignableWindow.posthogErrorWrappingFunctions = posthogErrorWrappingFunctions;
var extendPostHogWithExceptionAutocapture = function (instance, response) {
    if (!(0, core_1.isFunction)(instance === null || instance === void 0 ? void 0 : instance.capture)) {
        return;
    }
    var autocaptureExceptions = response === null || response === void 0 ? void 0 : response.autocaptureExceptions;
    var errorsToIgnore = !(0, core_1.isNull)(autocaptureExceptions) &&
        typeof autocaptureExceptions === 'object' &&
        (0, core_1.isArray)(autocaptureExceptions.errors_to_ignore)
        ? autocaptureExceptions.errors_to_ignore.reduce(function (rules, rule) {
            try {
                rules.push(new RegExp(rule));
            }
            catch (error) {
                logger.error('Ignoring invalid legacy exception exclusion rule', rule, error);
            }
            return rules;
        }, [])
        : [];
    var sendExceptionEvent = function (properties) {
        var _a;
        try {
            (_a = instance.capture) === null || _a === void 0 ? void 0 : _a.call(instance, '$exception', properties, {
                _noTruncate: true,
                _batchKey: 'exceptionEvent',
                _noHeatmaps: true,
            });
        }
        catch (error) {
            logger.error('Failed to capture exception for a legacy client', error);
        }
    };
    var captureException = function (properties) {
        if (errorsToIgnore.some(function (regex) {
            return properties.$exception_list.some(function (exception) { return regex.test(exception.value || ''); });
        })) {
            return;
        }
        sendExceptionEvent(properties);
    };
    wrapOnError(captureException);
    wrapUnhandledRejection(sendExceptionEvent, true);
};
globals_2.assignableWindow.extendPostHogWithExceptionAutoCapture = extendPostHogWithExceptionAutocapture;
globals_2.assignableWindow.extendPostHogWithExceptionAutocapture = extendPostHogWithExceptionAutocapture;
exports.default = posthogErrorWrappingFunctions;
//# sourceMappingURL=exception-autocapture.js.map