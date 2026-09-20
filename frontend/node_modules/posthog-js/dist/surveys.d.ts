import { PostHog } from './module';
import { DisplaySurveyType, SurveyPosition, Survey, SurveyWithTypeAndAppearance } from '@posthog/browser-common';
import { SurveyResponseValue as SurveyResponseValue$1 } from '@posthog/core';
import { Properties } from '@posthog/types';

/**
 * Having Survey types in types.ts was confusing tsc
 * and generating an invalid module.d.ts
 * See https://github.com/PostHog/posthog-js/issues/698
 */

type SurveyCallback = (surveys: Survey[], context?: {
    isLoaded: boolean;
    error?: string;
}) => void;
interface DisplaySurveyOptionsBase {
    /**
     * Whether to bypass the survey's targeting and display conditions.
     * @default false
     */
    ignoreConditions: boolean;
    /**
     * Whether to bypass the survey's configured popup delay.
     * @default false
     */
    ignoreDelay: boolean;
    /**
     * How the survey should be displayed.
     * @default DisplaySurveyType.Popover
     */
    displayType: DisplaySurveyType;
    /** Additional properties to include in all survey events (shown, sent, dismissed). */
    properties?: Properties;
    /** Pre-filled responses by question index (0-based). Only supported for popover surveys. */
    initialResponses?: Record<number, SurveyResponseValue>;
}
/** Options for displaying a survey as a popover. */
interface DisplaySurveyPopoverOptions extends DisplaySurveyOptionsBase {
    displayType: typeof DisplaySurveyType.Popover;
    /** Override the survey's configured position. */
    position?: SurveyPosition;
    /** CSS selector for the element to position the survey next to (when position is NextToTrigger). */
    selector?: string;
    /** When true, `survey shown` events will not be emitted automatically. */
    skipShownEvent?: boolean;
}
type SurveyResponseValue = SurveyResponseValue$1;

declare class SurveyManager {
    private _posthog;
    private _surveyInFocus;
    private _surveyTimeouts;
    private _widgetSelectorListeners;
    private _renderedTargets;
    private _prefillHandledSurveys;
    private _automaticDisplayDispose?;
    private _currentLanguage;
    private _surveyIsRendered;
    private _languageChangeListener;
    private _unsubscribeFeatureFlags;
    private _surveyPopupProps;
    private _displayOptions;
    constructor(posthog: PostHog);
    private _onLanguageChange;
    private get _featureFlags();
    private _applyDisplayOverrides;
    handlePageUnload: () => void;
    private _clearSurveyTimeout;
    /**
     * cancel a "pending" survey, i.e. one that is waiting to be displayed in
     * the _surveyTimeouts queue
     */
    cancelSurvey(surveyId: string): void;
    setAutomaticDisplayDispose(dispose: () => void): void;
    dispose(): void;
    /**
     * `resumeDelayFromActivation` is internal to the display loop: a survey armed by an
     * event/action trigger resumes its popup delay from when the trigger fired, so navigating
     * mid-delay does not restart the countdown. An explicit `displaySurvey()` call carries its own
     * `ignoreDelay` option instead, so it must always honor the full configured delay.
     */
    handlePopoverSurvey: (surveyParam: Survey, options?: DisplaySurveyPopoverOptions, { resumeDelayFromActivation }?: {
        resumeDelayFromActivation?: boolean;
    }) => void;
    private _handleWidget;
    private _detachWidgetSelectorListener;
    private _removeWidgetSelectorListener;
    private _isWidgetSurveyOpen;
    private _manageWidgetSelectorListener;
    /**
     * Sorts surveys by their appearance delay in ascending order. If a survey does not have an appearance delay,
     * it is considered to have a delay of 0.
     * @param surveys
     * @returns The surveys sorted by their appearance delay
     */
    private _sortSurveysByAppearanceDelay;
    renderPopover: (survey: Survey) => void;
    renderSurvey: (survey: Survey, selector: Element, properties?: Properties) => void;
    private _translateSurveyForRendering;
    private _handleUrlPrefill;
    /**
     * On load, capture a response for prefilled questions only when:
     * 1) the survey is complete, OR
     * 2) partial responses are enabled AND the skipped questions were set to auto-submit.
     */
    private _autoSubmitPrefilledResponses;
    /**
     * process prefilled responses for non-hosted surveys
     *
     * @returns boolean, true if the survey is completed
     */
    private _handleInitialResponses;
    private _processPrefillData;
    private _isSurveyFeatureFlagEnabled;
    private _isSurveyConditionMatched;
    private _internalFlagCheckSatisfied;
    checkSurveyEligibility(survey: Survey): {
        eligible: boolean;
        reason?: string;
    };
    /**
     * Renderability = eligibility (running, type, flags, wait period, already-seen) plus the
     * survey's event/action activation trigger. Used by the programmatic `canRenderSurvey` /
     * `canRenderSurveyAsync` checks so they match the display loop.
     *
     * The trigger is intentionally kept out of `checkSurveyEligibility`: that method is also
     * used by the explicit `displaySurvey` path, and the trigger state only lives in memory
     * (a reload clears it, server-side events never set it). Gating eligibility on it would
     * make explicit `displaySurvey('id')` calls silently show nothing.
     */
    checkSurveyRenderability(survey: Survey): {
        eligible: boolean;
        reason?: string;
    };
    /**
     * Surveys can be activated by events or actions. This method checks if the survey has events and actions,
     * and if so, it checks if the survey has been activated.
     * @param survey
     */
    private _hasActionOrEventTriggeredSurvey;
    private _checkFlags;
    /**
     * The full predicate for "should this survey display right now": eligibility (running,
     * type, linked/targeting/internal flags, wait period, already-seen) plus the URL/device/
     * selector conditions, the event/action trigger, and any feature-flag dependencies.
     *
     * Shared by the display loop and re-checked when a popover's delay timer fires, so a
     * survey that became ineligible *during* the delay (e.g. an identify() reloaded flags and
     * the internal targeting flag is now false) is not shown. Note this is purely an AND gate:
     * adding it can only ever suppress a display, never cause an extra one.
     */
    private _shouldDisplaySurvey;
    getActiveMatchingSurveys: (callback: SurveyCallback, forceReload?: boolean) => void;
    callSurveysAndEvaluateDisplayLogic: (forceReload?: boolean) => void;
    private _addSurveyToFocus;
    private _removeSurveyFromDom;
    private _removeSurveyFromFocus;
    getTestAPI(): {
        addSurveyToFocus: (survey: Pick<Survey, "id">) => void;
        removeSurveyFromFocus: (survey: SurveyWithTypeAndAppearance) => void;
        surveyInFocus: string | null;
        surveyTimeouts: Map<string, number>;
        handleWidget: (survey: Survey) => void;
        handlePopoverSurvey: (surveyParam: Survey, options?: DisplaySurveyPopoverOptions, { resumeDelayFromActivation }?: {
            resumeDelayFromActivation?: boolean;
        }) => void;
        manageWidgetSelectorListener: (survey: Survey, selector: string) => void;
        sortSurveysByAppearanceDelay: (surveys: Survey[]) => Survey[];
        checkFlags: (survey: Survey) => boolean;
        isSurveyFeatureFlagEnabled: (flagKey: string | null, flagVariant?: string | undefined) => boolean;
        onLanguageChange: () => void;
        currentLanguage: string | null;
        surveyIsRendered: boolean;
    };
}
declare function generateSurveys(posthog: PostHog, isSurveysEnabled: boolean | undefined): SurveyManager | undefined;

export { generateSurveys as default };
