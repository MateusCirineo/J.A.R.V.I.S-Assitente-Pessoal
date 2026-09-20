"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.setupSegmentIntegration = setupSegmentIntegration;
var logger_1 = require("@posthog/browser-common/utils/logger");
var constants_1 = require("../constants");
var core_1 = require("@posthog/core");
var uuidv7_1 = require("@posthog/browser-common/utils/uuidv7");
var logger = (0, logger_1.createLogger)('[SegmentIntegration]');
var createSegmentIntegration = function (posthog, runtimeAnonymousId) {
    if (typeof Promise === 'undefined' || !Promise.resolve) {
        logger.warn('This browser does not have Promise support, and can not use the segment integration');
    }
    var enrichEvent = function (ctx, eventName) {
        if (!eventName) {
            return ctx;
        }
        var preserveRuntimeAnonymousIdentity = !!runtimeAnonymousId && ctx.event.anonymousId === runtimeAnonymousId && !ctx.event.userId;
        if (!preserveRuntimeAnonymousIdentity &&
            !ctx.event.userId &&
            ctx.event.anonymousId !== posthog.get_distinct_id()) {
            // This is our only way of detecting that segment's analytics.reset() has been called so we also call it
            logger.info('No userId set, resetting PostHog');
            posthog.reset();
        }
        if (!preserveRuntimeAnonymousIdentity) {
            runtimeAnonymousId = undefined;
        }
        if (ctx.event.userId && ctx.event.userId !== posthog.get_distinct_id()) {
            logger.info('UserId set, identifying with PostHog');
            posthog.identify(ctx.event.userId);
        }
        var additionalProperties = posthog.calculateEventProperties(eventName, ctx.event.properties);
        ctx.event.properties = Object.assign({}, additionalProperties, ctx.event.properties);
        return ctx;
    };
    return {
        name: 'PostHog JS',
        type: 'enrichment',
        version: '1.0.0',
        isLoaded: function () { return true; },
        // check and early return above
        // oxlint-disable-next-line compat/compat
        load: function () { return Promise.resolve(); },
        track: function (ctx) { return enrichEvent(ctx, ctx.event.event); },
        page: function (ctx) { return enrichEvent(ctx, constants_1.EVENT_PAGEVIEW); },
        identify: function (ctx) { return enrichEvent(ctx, constants_1.EVENT_IDENTIFY); },
        screen: function (ctx) { return enrichEvent(ctx, '$screen'); },
    };
};
function setupPostHogFromSegment(posthog, done, bootstrapIdentifiedUser) {
    var segment = posthog.config.segment;
    if (!segment) {
        return done();
    }
    var bootstrapUser = function (user) {
        // Use segments anonymousId instead
        var getSegmentAnonymousId = function () { return user.anonymousId() || (0, uuidv7_1.uuidv7)(); };
        posthog.config.get_device_id = getSegmentAnonymousId;
        // During init, adopt an existing Segment user before PostHog starts loading events.
        // When Segment is configured later, the enrichment plugin handles the identity transition
        // so identify() can merge events captured before Segment was available.
        if (bootstrapIdentifiedUser && user.id()) {
            posthog.register({
                distinct_id: user.id(),
                $device_id: getSegmentAnonymousId(),
            });
            posthog.persistence.set_property(constants_1.USER_STATE, constants_1.USER_STATE_IDENTIFIED);
        }
        done(bootstrapIdentifiedUser ? undefined : user.anonymousId() || undefined);
    };
    var segmentUser = segment.user();
    if ('then' in segmentUser && (0, core_1.isFunction)(segmentUser.then)) {
        segmentUser.then(bootstrapUser);
    }
    else {
        bootstrapUser(segmentUser);
    }
}
function setupSegmentIntegration(posthog, done, bootstrapIdentifiedUser) {
    if (bootstrapIdentifiedUser === void 0) { bootstrapIdentifiedUser = true; }
    var segment = posthog.config.segment;
    if (!segment) {
        return done();
    }
    setupPostHogFromSegment(posthog, function (runtimeAnonymousId) {
        segment.register(createSegmentIntegration(posthog, runtimeAnonymousId)).then(function () {
            done();
        }, function (error) {
            logger.error('Failed to register the Segment integration', error);
            done();
        });
    }, bootstrapIdentifiedUser);
}
//# sourceMappingURL=segment-integration.js.map