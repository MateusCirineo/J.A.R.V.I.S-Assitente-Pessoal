"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MutableFeatureFlagsConfigSource = void 0;
var logger_1 = require("@posthog/browser-common/utils/logger");
var core_1 = require("@posthog/core");
var logger = (0, logger_1.createLogger)('[FeatureFlags]');
var DEFAULT_REFRESH_INTERVAL_MS = 5 * 60 * 1000;
var snapshot = function (config, remoteRequestsDisabled) {
    var _a, _b, _c, _d, _e;
    return ({
        bootstrap: {
            featureFlags: (_a = config.bootstrap) === null || _a === void 0 ? void 0 : _a.featureFlags,
            featureFlagPayloads: (_b = config.bootstrap) === null || _b === void 0 ? void 0 : _b.featureFlagPayloads,
        },
        remoteRequestsDisabled: remoteRequestsDisabled,
        featureFlagsDisabled: !!config.advanced_disable_feature_flags,
        onlyEvaluateSurveyFeatureFlags: !!config.advanced_only_evaluate_survey_feature_flags,
        deduplicateCallsPerSession: !!config.advanced_feature_flags_dedup_per_session,
        cacheTtlMs: config.feature_flag_cache_ttl_ms,
        refreshIntervalMs: (_c = config.remote_config_refresh_interval_ms) !== null && _c !== void 0 ? _c : DEFAULT_REFRESH_INTERVAL_MS,
        requestTimeoutMs: config.feature_flag_request_timeout_ms,
        compression: config.disable_compression ? undefined : 'best-available',
        evaluationContexts: (_e = (_d = config.evaluation_contexts) !== null && _d !== void 0 ? _d : config.evaluation_environments) !== null && _e !== void 0 ? _e : [],
        flagKeys: (0, core_1.isArray)(config.flag_keys) ? config.flag_keys : undefined,
    });
};
/** Mutable browser-v1 mapping kept outside the extension-facing config source. */
var MutableFeatureFlagsConfigSource = /** @class */ (function () {
    function MutableFeatureFlagsConfigSource(config, remoteRequestsDisabled) {
        if (remoteRequestsDisabled === void 0) { remoteRequestsDisabled = false; }
        this._loggedEvaluationEnvironmentsDeprecation = false;
        this.update(config, remoteRequestsDisabled);
    }
    MutableFeatureFlagsConfigSource.prototype.update = function (config, remoteRequestsDisabled) {
        this._snapshot = snapshot(config, remoteRequestsDisabled);
        if (config.evaluation_environments &&
            !config.evaluation_contexts &&
            !this._loggedEvaluationEnvironmentsDeprecation) {
            logger.warn('evaluation_environments is deprecated. Use evaluation_contexts instead. evaluation_environments will be removed in a future version.');
            this._loggedEvaluationEnvironmentsDeprecation = true;
        }
        if (!(0, core_1.isUndefined)(config.flag_keys) && !(0, core_1.isArray)(config.flag_keys)) {
            logger.error('Invalid flag_keys found:', config.flag_keys, 'Expected array of non-empty strings');
        }
    };
    MutableFeatureFlagsConfigSource.prototype.get = function () {
        return this._snapshot;
    };
    return MutableFeatureFlagsConfigSource;
}());
exports.MutableFeatureFlagsConfigSource = MutableFeatureFlagsConfigSource;
//# sourceMappingURL=feature-flags-config.js.map