from enum import IntFlag

import comtypes.gen._C866CA3A_32F7_11D2_9602_00C04F8EE628_0_5_4 as __wrapper_module__
from comtypes.gen._C866CA3A_32F7_11D2_9602_00C04F8EE628_0_5_4 import (
    SVPOver, _ISpeechRecoContextEvents, SPTEXTSELECTIONINFO,
    eLEXTYPE_PRIVATE15, eLEXTYPE_PRIVATE5, SPEI_MIN_TTS,
    SREAudioLevel, DISPMETHOD, SVSFPersistXML, SpAudioFormat,
    SAFT8kHz8BitMono, SpNullPhoneConverter, DISPID_SRCRequestedUIType,
    SPSMF_SRGS_SAPIPROPERTIES, DISPID_SDKGetlongValue,
    DISPID_SRRAlternates, ISpeechGrammarRuleState, SPGS_DISABLED,
    DISPID_SMSADeviceId, SPPS_Modifier, SDTRule, SDKLDefaultLocation,
    SSSPTRelativeToEnd, SPVOICESTATUS, SAFTCCITT_ALaw_44kHzMono,
    SPEI_TTS_BOOKMARK, DISPID_SRGRules, DISPID_SGRSAddWordTransition,
    SPBINARYGRAMMAR, ISpStreamFormatConverter,
    SPWORDPRONUNCIATIONLIST, SpeechAudioVolume, DISPID_SVSpeakStream,
    eLEXTYPE_PRIVATE17, SPSMF_UPS, SRATopLevel,
    ISpeechRecognizerStatus, SPEI_UNDEFINED, SPGS_EXCLUSIVE,
    DISPID_SPRuleEngineConfidence, __MIDL_IWinTypes_0009,
    DISPID_SPRs_NewEnum, ISpeechMemoryStream, SPEI_END_SR_STREAM,
    ISpRecognizer3, SRAImport, DISPID_SPRsCount,
    ISpeechPhraseProperties, SPEI_START_SR_STREAM, SPEI_RESERVED6,
    DISPID_SDKOpenKey, ISpeechPhraseReplacements,
    SGDSActiveUserDelimited, SAFT32kHz8BitMono, ISpeechRecoResult,
    DISPID_SMSSetData, SAFT32kHz8BitStereo, DISPID_SVStatus,
    SPRS_ACTIVE_WITH_AUTO_PAUSE, SP_VISEME_21, DISPID_SAEventHandle,
    SAFTADPCM_22kHzMono, DISPID_SRSCurrentStreamNumber, ISpDataKey,
    SpeechAudioProperties, eLEXTYPE_VENDORLEXICON,
    DISPID_SWFEAvgBytesPerSec, DISPID_SRSAudioStatus,
    SVEEndInputStream, SPEI_MAX_SR, eLEXTYPE_RESERVED9, SVP_13, SVP_3,
    SPPS_SuppressWord, SPCS_ENABLED, SPRST_INACTIVE, SLTUser,
    DISPID_SGRsItem, SVEAllEvents, SPPS_Unknown, DISPID_SGRSTText,
    SPINTERFERENCE_TOOSLOW, SPSHT_OTHER, ISpRecoCategory,
    DISPID_SREmulateRecognition, DISPID_SVPause, DISPID_SPPConfidence,
    SpeechMicTraining, SPPS_Interjection, SPFM_OPEN_READWRITE,
    ISpeechPhraseInfoBuilder, SPLO_STATIC, SVEPhoneme,
    DISPID_SVSLastBookmark, SPSSuppressWord,
    DISPID_SRAllowVoiceFormatMatchingOnNextSet,
    ISpeechObjectTokenCategory, SPINTERFERENCE_NONE,
    DISPID_SDKGetStringValue, DISPID_SVSkip, helpstring, SWTDeleted,
    SITooFast, SpeechPropertyNormalConfidenceThreshold, SRSEDone,
    DISPID_SRGCmdLoadFromResource, SpObjectToken,
    DISPID_SRSSupportedLanguages, SRCS_Enabled,
    DISPID_SPEEngineConfidence, _ULARGE_INTEGER, SPDKL_CurrentConfig,
    DISPID_SASCurrentSeekPosition, WAVEFORMATEX, SVF_None,
    SGSExclusive, DISPID_SPAPhraseInfo, SRERecognition,
    ISpStreamFormat, DISPID_SPRulesItem, SPWORDPRONUNCIATION,
    SpWaveFormatEx, DISPID_SLGetGenerationChange, DISPID_SVSVisemeId,
    DISPID_SVAudioOutput, DISPID_SLAddPronunciationByPhoneIds,
    DISPID_SPIProperties, SPAUDIOSTATUS, SDTProperty, SVP_4,
    eLEXTYPE_PRIVATE6, SP_VISEME_0, DISPID_SRIsShared,
    SpeechGrammarTagWildcard, IStream, DISPID_SRGetFormat,
    DISPID_SRGId, SPRS_ACTIVE_USER_DELIMITED, SpPhoneConverter,
    SpeechCategoryRecognizers, DISPID_SOTCEnumerateTokens,
    DISPID_SPRules_NewEnum, STCRemoteServer, SVF_Emphasis,
    DISPID_SRRTTickCount, SRAInterpreter,
    DISPID_SRCERecognizerStateChange, DISPID_SPPs_NewEnum,
    DISPID_SRGCommit, SpeechGrammarTagUnlimitedDictation,
    SpeechEngineProperties, SAFTADPCM_8kHzStereo,
    DISPID_SABIMinNotification, DISPIDSPTSI_SelectionOffset,
    SECFIgnoreKanaType, DISPID_SOTGetDescription, DISPID_SABufferInfo,
    ULONG_PTR, SVPAlert, DISPID_SRCEStartStream, SPEI_VOICE_CHANGE,
    SECHighConfidence, SPBO_PAUSE, DISPID_SRCVoice,
    DISPID_SRCBookmark, ISpRecoResult, SPAS_RUN, DISPID_SPRsItem,
    SRERecoOtherContext, SAFTADPCM_44kHzMono, DISPID_SGRSTPropertyId,
    eLEXTYPE_PRIVATE14, DISPID_SPRulesCount, SDTReplacement,
    STSF_LocalAppData, STSF_AppData, ISpeechGrammarRules, SRAONone,
    DISPID_SLGetWords, SAFTADPCM_8kHzMono, SPPS_Verb, SPVPRI_OVER,
    DISPID_SRCEPropertyStringChange, SVP_1, SPWF_INPUT,
    DISPID_SDKSetBinaryValue, DISPID_SRCEBookmark,
    DISPID_SRGRecoContext, DISPID_SPIAudioSizeTime,
    DISPID_SAFSetWaveFormatEx, DISPID_SGRSTNextState,
    _ISpeechVoiceEvents, SpeechPropertyResponseSpeed,
    SpeechPropertyLowConfidenceThreshold,
    SPWP_UNKNOWN_WORD_UNPRONOUNCEABLE, SpMemoryStream,
    DISPID_SPELexicalForm, SAFT44kHz8BitMono, DISPID_SGRSTs_NewEnum,
    DISPID_SLGetPronunciations, SpeechCategoryPhoneConverters,
    SpeechAudioFormatGUIDText, DISPID_SAFGuid,
    DISPID_SGRSTPropertyValue, VARIANT, ISpeechLexiconWords,
    DISPID_SGRsCommit, SVSFUnusedFlags, ISpRecoContext,
    ISpResourceManager, DISPID_SGRsCount, DISPID_SGRSTsCount,
    SPAR_Medium, DISPID_SVSInputWordLength, SPRECOGNIZERSTATUS,
    DISPID_SRCEFalseRecognition, SINone, SVP_10, DISPID_SBSSeek,
    SpStream, SPPS_Noncontent, typelib_path, DISPID_SADefaultFormat,
    SPWT_LEXICAL_NO_SPECIAL_CHARS, SAFTGSM610_22kHzMono,
    DISPID_SLRemovePronunciationByPhoneIds, DISPID_SLPType,
    DISPID_SLAddPronunciation, SPAR_Low, SVSFNLPSpeakPunc,
    DISPID_SVEStreamStart, SVP_6, SRADynamic, DISPID_SOTsCount,
    DISPID_SPIGetText, SVP_20, DISPID_SRRAudio, SRAExport,
    DISPID_SPCPhoneToId, DISPID_SGRAddState,
    DISPID_SPEDisplayAttributes, SPRST_NUM_STATES, SPCT_SUB_DICTATION,
    ISpeechPhraseReplacement, SREStateChange,
    DISPID_SOTMatchesAttributes, ISpeechMMSysAudio, SPEI_RESERVED3,
    SpeechTokenKeyUI, DISPID_SRGCmdSetRuleState, SAFT24kHz16BitStereo,
    DISPID_SRRSpeakAudio, DISPID_SPRuleChildren, SECFIgnoreCase,
    SPEI_RESERVED1, SAFTNoAssignedFormat, SAFT11kHz16BitStereo,
    DISPID_SPRuleName, eLEXTYPE_MORPHOLOGY, SPSInterjection,
    DISPID_SPRuleParent, SRERequestUI, SVSFNLPMask, DISPID_SPPsCount,
    SpInProcRecoContext, SP_VISEME_1, eWORDTYPE_DELETED, SPSNoun,
    SpeechDictationTopicSpelling, STCLocalServer, SPPS_RESERVED1,
    DISPID_SRRTimes, SpeechTokenValueCLSID, DISPID_SGRSTPropertyName,
    eLEXTYPE_PRIVATE1, SPSEMANTICERRORINFO,
    SAFTCCITT_uLaw_44kHzStereo, DISPID_SVEWord, ISpeechVoiceStatus,
    DISPID_SRCEInterference, DISPID_SVEPhoneme,
    SAFTCCITT_ALaw_8kHzMono, DISPID_SOTCDefault,
    ISpeechLexiconPronunciation, DISPID_SBSFormat, SPSHT_EMAIL,
    SVP_11, ISpeechAudioFormat, SGLexical, ISpPhrase,
    SpeechPropertyComplexResponseSpeed, ISpeechPhraseRules,
    SpNotifyTranslator, DISPID_SDKEnumValues,
    DISPID_SRCSetAdaptationData, DISPID_SPIReplacements, ISpAudio,
    SAFTADPCM_44kHzStereo, SDTAlternates,
    SpeechRegistryLocalMachineRoot, ISpNotifyTranslator,
    DISPID_SPRText, DISPID_SAFGetWaveFormatEx, SAFT22kHz16BitMono,
    SPAS_PAUSE, SPEI_SR_RETAINEDAUDIO, SRTReSent,
    SPEI_RECO_OTHER_CONTEXT, SPDKL_CurrentUser, SPPHRASEPROPERTY,
    DISPID_SRGCmdLoadFromMemory, SVSFDefault, SITooLoud,
    SPEVENTSOURCEINFO, Speech_Max_Pron_Length, DISPID_SGRAddResource,
    DISPID_SPIEnginePrivateData, SGSEnabled, ISpeechPhraseProperty,
    SPEI_START_INPUT_STREAM, SpVoice, DISPID_SVSInputSentencePosition,
    SVESentenceBoundary, DISPID_SPEAudioStreamOffset,
    DISPID_SPEPronunciation, ISpeechAudioStatus,
    SAFTCCITT_uLaw_22kHzMono, SAFT32kHz16BitStereo, SPPHRASEELEMENT,
    SPFM_CREATE_ALWAYS, SPPS_Noun, SPWP_UNKNOWN_WORD_PRONOUNCEABLE,
    SpeechTokenIdUserLexicon, DISPID_SOTSetId,
    DISPID_SRSCurrentStreamPosition, SREPropertyNumChange,
    ISpeechLexicon, DISPID_SPEs_NewEnum, SBOPause,
    ISpObjectTokenCategory, ISpeechXMLRecoResult,
    __MIDL___MIDL_itf_sapi_0000_0020_0001, SpFileStream,
    DISPIDSPTSI_ActiveLength, SPEI_RESERVED5,
    DISPID_SVAudioOutputStream, SPEI_SR_PRIVATE, SPEI_MAX_TTS,
    SpeechVoiceSkipTypeSentence, SRARoot,
    SPINTERFERENCE_LATENCY_TRUNCATE_BEGIN, eLEXTYPE_RESERVED8,
    SPINTERFERENCE_NOSIGNAL, SpSharedRecoContext, DISPID_SRDisplayUI,
    SAFTGSM610_8kHzMono, DISPID_SLWType, SpeechCategoryVoices,
    Speech_Default_Weight, SAFTCCITT_ALaw_44kHzStereo,
    DISPID_SPAStartElementInResult, SPEI_END_INPUT_STREAM,
    SPSMF_SRGS_SEMANTICINTERPRETATION_MS, DISPID_SLWsItem,
    SPINTERFERENCE_TOOQUIET, IServiceProvider, SLTApp,
    SPRECOCONTEXTSTATUS, Speech_Max_Word_Length, SVP_9,
    SAFT24kHz8BitMono, SpPhoneticAlphabetConverter, SGRSTTWord,
    DISPID_SLRemovePronunciation, DISPID_SVAlertBoundary,
    DISPID_SRGState, DISPID_SLPsCount, DISPID_SRCRetainedAudio,
    SP_VISEME_14, eLEXTYPE_RESERVED7, DISPID_SVGetAudioInputs,
    SPSMF_SAPI_PROPERTIES, DISPID_SPISaveToMemory,
    DISPID_SRRRecoContext, DISPID_SLPLangId,
    SAFTCCITT_uLaw_8kHzStereo, DISPID_SRSetPropertyNumber,
    SPEI_SOUND_END, SVEVoiceChange, DISPID_SLPPartOfSpeech,
    ISpeechObjectTokens, SSFMOpenReadWrite,
    SpTextSelectionInformation, Library, DISPID_SPPId, SREAdaptation,
    DISPID_SWFESamplesPerSec, SECFDefault, SP_VISEME_5,
    SAFT8kHz16BitMono, ISpRecoGrammar, SDTPronunciation,
    DISPID_SVESentenceBoundary, DISPID_SVEBookmark, SLOStatic,
    ISpeechGrammarRuleStateTransitions, STCInprocHandler,
    eLEXTYPE_PRIVATE13, STSF_FlagCreate, ISpPhraseAlt,
    DISPID_SRSClsidEngine, SAFT16kHz16BitMono, DISPID_SRRecognizer,
    SVP_7, SPSFunction, SAFT22kHz8BitMono, SPCS_DISABLED,
    DISPID_SFSClose, ISpObjectWithToken, SSTTTextBuffer,
    DISPID_SRGCmdSetRuleIdState, SVSFParseSapi,
    DISPID_SRGetPropertyString, eLEXTYPE_PRIVATE19,
    DISPID_SRCEAdaptation, SPPS_LMA, DISPID_SDKSetStringValue,
    DISPID_SOTCSetId, SpeechCategoryRecoProfiles, SPSVerb,
    SpeechTokenKeyFiles, DISPID_SVEAudioLevel, DISPID_SGRSRule,
    SVP_14, DISPID_SOTDisplayUI, SpInprocRecognizer,
    SAFT22kHz16BitStereo, SpStreamFormatConverter,
    ISpeechWaveFormatEx, DISPID_SVPriority, SPEI_SR_BOOKMARK,
    DISPID_SGRsAdd, SPEI_TTS_AUDIO_LEVEL, SP_VISEME_7,
    eLEXTYPE_PRIVATE2, SDTLexicalForm, DISPID_SVSCurrentStreamNumber,
    DISPIDSPTSI_ActiveOffset, SAFT44kHz16BitStereo, SASStop, GUID,
    DISPID_SRAllowAudioInputFormatChangesOnNextSet,
    SGDSActiveWithAutoPause, DISPID_SOTCId, SpResourceManager,
    SPGS_ENABLED, DISPID_SPAs_NewEnum, DISPID_SPEDisplayText,
    DISPID_SPIAudioSizeBytes, DISPID_SRCEventInterests,
    DISPID_SOTCGetDataKey, SAFTADPCM_11kHzMono, SVSFIsNotXML,
    SAFT16kHz16BitStereo, ISpShortcut, dispid, SAFTADPCM_11kHzStereo,
    DISPID_SPACommit, DISPID_SGRName, SP_VISEME_15,
    SpeechPropertyResourceUsage, SAFT22kHz8BitStereo, HRESULT,
    DISPID_SVRate, SPRULE, DISPID_SVGetAudioOutputs, SRSEIsSpeaking,
    DISPID_SRCVoicePurgeEvent, DISPID_SGRsDynamic, DISPID_SPIRule,
    SVP_15, WSTRING, DISPID_SRCreateRecoContext,
    DISPID_SASNonBlockingIO, eLEXTYPE_PRIVATE20, DISPID_SBSWrite,
    DISPID_SVEVoiceChange, LONG_PTR, SITooSlow,
    SWPUnknownWordPronounceable, DISPID_SRSNumberOfActiveRules,
    DISPID_SAFType, SPBO_NONE, ISpPhoneConverter, ISpeechVoice,
    SAFT11kHz8BitMono, SAFT12kHz8BitMono, DISPID_SVSRunningState,
    SAFTGSM610_11kHzMono, STCAll, DISPID_SPPBRestorePhraseFromMemory,
    SVSFParseMask, SPRS_INACTIVE, DISPID_SRGCmdLoadFromFile,
    SPAO_RETAIN_AUDIO, SGSDisabled, DISPID_SOTIsUISupported,
    DISPIDSPTSI_SelectionLength, ISpRecognizer2, DISPID_SOTCategory,
    SPINTERFERENCE_LATENCY_TRUNCATE_END, DISPID_SRCState,
    SpMMAudioOut, DISPID_SPERequiredConfidence, UINT_PTR,
    DISPID_SPPChildren, SWPUnknownWordUnpronounceable, ISpEventSink,
    SP_VISEME_19, SRSInactive, SpMMAudioIn, SPXRO_Alternates_SML,
    SAFTCCITT_ALaw_22kHzMono, SP_VISEME_10,
    DISPID_SRCERecognitionForOtherContext, SWPKnownWordPronounceable,
    ISpeechAudio, DISPID_SVAllowAudioOuputFormatChangesOnNextSet,
    SVP_16, DISPID_SRCPause, SFTSREngine, SpCustomStream,
    SGRSTTWildcard, eLEXTYPE_RESERVED4, SAFTCCITT_uLaw_11kHzMono,
    SPINTERFERENCE_NOISE, SPRS_ACTIVE, DISPID_SGRSTRule,
    SPEI_SR_AUDIO_LEVEL, DISPID_SRGetRecognizers, SVEAudioLevel,
    ISpRecoContext2, SPXRO_SML, DISPID_SGRsCommitAndSave,
    SAFT16kHz8BitMono, SDTAll, SpeechPropertyAdaptationOn, SBONone,
    DISPID_SRCEAudioLevel, ISpEventSource, SPWT_DISPLAY,
    SPRST_INACTIVE_WITH_PURGE, SPPS_Function, SPDKL_LocalMachine,
    DISPID_SPERetainedStreamOffset, SAFTCCITT_uLaw_22kHzStereo,
    DISPID_SRRTStreamTime, SPWT_PRONUNCIATION, SPEI_TTS_PRIVATE,
    DISPID_SRGIsPronounceable, SPEI_SOUND_START, SPSHORTCUTPAIRLIST,
    SRSActive, DISPID_SPIElements, SREFalseRecognition,
    DISPID_SRCEHypothesis, SECFIgnoreWidth, DISPID_SPIGrammarId,
    SP_VISEME_12, DISPID_SABufferNotifySize, SVSFPurgeBeforeSpeak,
    eLEXTYPE_LETTERTOSOUND, DISPID_SVGetProfiles,
    ISpeechPhraseElement, SP_VISEME_2, DISPID_SDKEnumKeys,
    SPEI_WORD_BOUNDARY, DISPID_SLPsItem, ISpNotifySink,
    DISPID_SRCEEnginePrivate, SPWF_SRENGINE, wireHWND,
    SGRSTTDictation, DISPID_SRRSetTextFeedback, DISPID_SLWs_NewEnum,
    ISpNotifySource, SVP_5, SPEI_VISEME, DISPID_SRGDictationUnload,
    SDKLCurrentUser, DISPID_SGRAttributes, SVP_12,
    DISPID_SOTs_NewEnum, eLEXTYPE_PRIVATE12, DISPID_SDKGetBinaryValue,
    ISpSerializeState, DISPID_SPPFirstElement, SAFT24kHz8BitStereo,
    ISpMMSysAudio, eLEXTYPE_PRIVATE7, SpeechCategoryAppLexicons,
    DISPID_SGRsFindRule, SWTAdded, SPPHRASERULE, SpSharedRecognizer,
    DISPID_SPARecoResult, DISPID_SPEsCount, DISPID_SGRSTType,
    DISPID_SGRSTransitions, SVP_17, DISPID_SPPName, SPBO_AHEAD,
    SPVPRI_NORMAL, ISpPhoneticAlphabetSelection, SRESoundEnd,
    DISPID_SRRPhraseInfo, SGRSTTEpsilon, SRTExtendableParse,
    SSFMCreateForWrite, SPEI_HYPOTHESIS, SP_VISEME_16, BSTR,
    ISpeechRecoResultDispatch, DISPID_SLWPronunciations,
    SpPhraseInfoBuilder, DISPID_SPRFirstElement, SINoSignal,
    DISPID_SRCCmdMaxAlternates, DISPID_SOTDataKey,
    DISPID_SLPs_NewEnum, SPEI_RECO_STATE_CHANGE, SREPrivate,
    SDA_No_Trailing_Space, DISPID_SPEActualConfidence,
    ISequentialStream, ISpObjectToken, SpeechTokenKeyAttributes,
    ISpeechRecoResultTimes, SREAllEvents, eLEXTYPE_PRIVATE4, SVP_18,
    DISPID_SGRSTsItem, DISPID_SRGDictationLoad,
    SSSPTRelativeToCurrentPosition, DISPID_SVSLastResult, IUnknown,
    DISPID_SLWLangId, SVEViseme, SVSFVoiceMask, SPEVENT,
    SpeechRecoProfileProperties, DISPID_SPIStartTime,
    SPEI_PROPERTY_NUM_CHANGE, SPAUDIOBUFFERINFO, SVSFParseAutodetect,
    DISPID_SABIBufferSize, DISPID_SMSGetData, COMMETHOD,
    DISPID_SVEStreamEnd, SDKLLocalMachine, SPPS_RESERVED2,
    DISPID_SOTGetStorageFileName, ISpeechPhraseAlternates,
    DISPID_SRGSetTextSelection, SAFT48kHz8BitMono, ISpeechRecoResult2,
    DISPID_SPRuleNumberOfElements, SAFTExtendedAudioFormat,
    SVSFParseSsml, IInternetSecurityManager, SP_VISEME_8,
    SpeechGrammarTagDictation, DISPID_SRCEEndStream,
    eLEXTYPE_PRIVATE18, SPAR_High, SVEPrivate, DISPID_SRCRecognizer,
    SPVPRI_ALERT, DISPID_SFSOpen, SPPS_RESERVED4, SVSFIsFilename,
    SPCT_SUB_COMMAND, DISPID_SVSLastStreamNumberQueued,
    DISPID_SRRAudioFormat, SGDisplay, DISPID_SAVolume,
    DISPID_SLWsCount, ISpeechLexiconPronunciations,
    SpeechPropertyHighConfidenceThreshold,
    DISPID_SPIRetainedSizeBytes, SAFT8kHz8BitStereo,
    SDA_One_Trailing_Space, SPSNotOverriden, DISPID_SPIEngineId,
    SAFTCCITT_ALaw_11kHzMono, eLEXTYPE_PRIVATE8, SVP_8,
    DISPID_SGRInitialState, DISPID_SASFreeBufferSpace, _lcid,
    DISPID_SPRDisplayAttributes, SpeechAllElements,
    DISPID_SVEEnginePrivate, SGRSTTRule, SPAO_NONE, CoClass,
    SRTStandard, SSTTWildcard, DISPID_SGRs_NewEnum, SP_VISEME_13,
    SDA_Consume_Leading_Spaces, SPSMF_SRGS_SEMANTICINTERPRETATION_W3C,
    SPDKL_DefaultLocation, ISpeechLexiconWord, SPSERIALIZEDRESULT,
    ISpeechAudioBufferInfo, ISpRecognizer, DISPID_SVEventInterests,
    SGLexicalNoSpecialChars, SAFTCCITT_uLaw_8kHzMono,
    DISPID_SPAsCount, DISPID_SPCLangId, DISPID_SLWWord, SSFMCreate,
    SREBookmark, SVF_Stressed, SAFTText, SP_VISEME_18,
    DISPID_SPERetainedSizeBytes, SAFTCCITT_ALaw_8kHzStereo,
    SREPropertyStringChange, eLEXTYPE_USER_SHORTCUT, DISPID_SRProfile,
    SPRST_ACTIVE_ALWAYS, SECFNoSpecialChars,
    ISpPhoneticAlphabetConverter, DISPID_SASCurrentDevicePosition,
    DISPID_SWFEChannels, SAFTCCITT_uLaw_44kHzMono, _check_version,
    DISPID_SWFEBlockAlign, SVEBookmark, SPAS_STOP, eLEXTYPE_PRIVATE16,
    DISPID_SOTRemove, SRTEmulated, SITooQuiet, DISPID_SPPsItem,
    DISPID_SRAudioInput, DISPID_SRCAudioInInterferenceStatus,
    DISPID_SGRClear, SPWORD, ISpeechTextSelectionInformation,
    SAFTNonStandardFormat, DISPID_SRGCmdLoadFromObject,
    ISpeechPhraseInfo, SAFT11kHz16BitMono, _FILETIME,
    ISpeechRecoGrammar, __MIDL___MIDL_itf_sapi_0000_0020_0002,
    DISPID_SRRGetXMLErrorInfo, DISPID_SRSetPropertyString, ISpVoice,
    SVP_0, DISPID_SVIsUISupported, DISPID_SPPParent,
    DISPID_SPANumberOfElementsInResult, DISPID_SMSALineId, SPSLMA,
    SPEI_INTERFERENCE, SVP_2, DISPID_SRRDiscardResultInfo,
    SP_VISEME_9, SAFT48kHz8BitStereo, SVPNormal, SRESoundStart,
    SpeechVoiceCategoryTTSRate, SREStreamStart, SpLexicon,
    SRTAutopause, SAFT44kHz16BitMono, SECNormalConfidence,
    SPWT_LEXICAL, SPSModifier, ISpeechBaseStream, SPCT_COMMAND,
    SAFT8kHz16BitStereo, SDTAudio, SPEI_FALSE_RECOGNITION,
    eLEXTYPE_RESERVED6, SPEI_PHRASE_START, SAFT44kHz8BitStereo,
    eLEXTYPE_RESERVED10, SINoise, SP_VISEME_11,
    SpeechAudioFormatGUIDWave, DISPID_SVEViseme,
    SpObjectTokenCategory, DISPID_SRCERecognition,
    DISPID_SRCESoundEnd, SGPronounciation, SVP_19,
    ISpeechResourceLoader, DISPID_SPRuleConfidence,
    tagSPTEXTSELECTIONINFO, DISPID_SVGetVoices, eLEXTYPE_PRIVATE9,
    DISPID_SDKDeleteValue, Speech_StreamPos_RealTime, SPSUnknown,
    SPEI_PROPERTY_STRING_CHANGE, SPEI_ACTIVE_CATEGORY_CHANGED,
    SASClosed, SVEWordBoundary, SAFT32kHz16BitMono,
    DISPID_SLGenerationId, SpeechUserTraining,
    DISPID_SPRuleFirstElement, eLEXTYPE_PRIVATE11,
    DISPID_SRRSaveToMemory, ISpProperties, SSSPTRelativeToStart,
    SDA_Two_Trailing_Spaces, eWORDTYPE_ADDED,
    SAFTCCITT_ALaw_22kHzStereo, SPSERIALIZEDPHRASE,
    SAFT16kHz8BitStereo, DISPID_SRCCreateGrammar, SGRSTTTextBuffer,
    SPRST_ACTIVE, SpeechRegistryUserRoot, SSTTDictation,
    DISPID_SABIEventBias, SAFT48kHz16BitMono, SGDSActive,
    SPEI_RECOGNITION, SPSHT_NotOverriden, DISPID_SPPValue,
    DISPID_SVResume, SFTInput, ISpXMLRecoResult,
    DISPID_SPPEngineConfidence, SAFTADPCM_22kHzStereo,
    DISPID_SOTCreateInstance, DISPID_SMSAMMHandle, SVSFIsXML,
    SPRECORESULTTIMES, DISPID_SDKSetLongValue, DISPID_SWFEFormatTag,
    IEnumString, SECLowConfidence, SpShortcut, SAFT12kHz16BitMono,
    SREInterference, SASPause, DISPID_SGRId, SVEStartInputStream,
    SASRun, DISPID_SRCCreateResultFromMemory, SAFT12kHz16BitStereo,
    DISPID_SAStatus, SPWP_KNOWN_WORD_PRONOUNCEABLE, SpMMAudioEnum,
    SRCS_Disabled, DISPID_SPEAudioSizeTime,
    DISPID_SGRSAddSpecialTransition, DISPID_SRCEPhraseStart,
    SAFTCCITT_uLaw_11kHzStereo, ISpeechRecoContext,
    DISPID_SOTRemoveStorageFileName, ISpLexicon,
    ISpeechGrammarRuleStateTransition, SPEI_SENTENCE_BOUNDARY,
    eLEXTYPE_PRIVATE3, ISpeechCustomStream,
    DISPID_SPPNumberOfElements, DISPID_SVSLastBookmarkId,
    SpeechCategoryAudioIn, SPPS_RESERVED3, DISPID_SPAsItem,
    ISpeechPhoneConverter, DISPID_SOTsItem, SPPROPERTYINFO,
    ISpeechRecognizer, ISpeechObjectToken,
    DISPID_SRGSetWordSequenceData, DISPID_SGRSTWeight,
    DISPID_SCSBaseStream, DISPID_SVVoice, DISPID_SPEAudioTimeOffset,
    ISpeechPhraseAlternate, SPAS_CLOSED, eLEXTYPE_APP,
    DISPID_SPIAudioStreamPosition, DISPID_SVSpeak, STCInprocServer,
    SP_VISEME_3, DISPID_SRCRetainedAudioFormat, SAFT48kHz16BitStereo,
    SPEI_MIN_SR, SPEI_RESERVED2, SRSActiveAlways, SPFM_CREATE,
    SREPhraseStart, SPFM_NUM_MODES, DISPID_SRAudioInputStream,
    SREStreamEnd, DISPID_SVVolume, DISPID_SWFEBitsPerSample,
    VARIANT_BOOL, SPEI_REQUEST_UI, SLODynamic, ISpeechDataKey,
    DISPID_SRState, SPCT_DICTATION, SpeechCategoryAudioOut,
    SPEI_ADAPTATION, SPINTERFERENCE_TOOLOUD, SVP_21, SRTSMLTimeout,
    SPEI_PHONEME, DISPID_SGRSAddRuleTransition,
    DISPID_SVSInputWordPosition, SPBO_TIME_UNITS, SDTDisplayText,
    DISPID_SPIGetDisplayAttributes, SpUnCompressedLexicon,
    SPLO_DYNAMIC, SPINTERFERENCE_LATENCY_WARNING, DISPID_SASetState,
    STSF_CommonAppData, SP_VISEME_20, _RemotableHandle,
    DISPID_SVWaitUntilDone, DISPID_SPILanguageId, SPSHT_Unknown,
    DISPID_SPCIdToPhone, tagSTATSTG, DISPID_SRCEPropertyNumberChange,
    SAFT12kHz8BitStereo, DISPID_SLPSymbolic, eLEXTYPE_USER,
    DISPID_SPRuleId, DISPID_SVSInputSentenceLength, DISPID_SOTId,
    SPPHRASE, DISPID_SRGReset, Speech_StreamPos_Asap,
    DISPID_SVSyncronousSpeakTimeout,
    DISPID_SRGCmdLoadFromProprietaryGrammar, tagSPPROPERTYINFO,
    SP_VISEME_17, DISPID_SRGetPropertyNumber, SPWORDLIST,
    ISpeechPhraseRule, DISPID_SPEAudioSizeBytes, DISPID_SRRTLength,
    SAFTGSM610_44kHzMono, ISpRecoGrammar2, DISPID_SRCResume,
    DISPID_SPEsItem, DISPID_SDKDeleteKey, ISpeechPhraseElements,
    SSFMOpenForRead, SAFT24kHz16BitMono, SPPHRASEREPLACEMENT,
    SPFM_OPEN_READONLY, DISPID_SOTGetAttribute, DISPID_SRCESoundStart,
    DISPID_SRRTOffsetFromStart, SPPS_NotOverriden, DISPID_SASState,
    SRADefaultToActive, DISPID_SRStatus, SPINTERFERENCE_TOOFAST,
    SAFT11kHz8BitStereo, IEnumSpObjectTokens, DISPID_SWFEExtraData,
    SP_VISEME_6, ISpGrammarBuilder, SPSHORTCUTPAIR, SECFEmulateResult,
    DISPID_SRIsUISupported, SRSInactiveWithPurge, ISpeechGrammarRule,
    SpCompressedLexicon, _LARGE_INTEGER, SVSFlagsAsync, SGDSInactive,
    DISPID_SVSpeakCompleteEvent, SPAR_Unknown,
    IInternetSecurityMgrSite, DISPID_SBSRead, DISPID_SLPPhoneIds,
    ISpStream, DISPID_SVSPhonemeId, eLEXTYPE_PRIVATE10,
    SAFTTrueSpeech_8kHz1BitMono, SRAORetainAudio, ISpeechFileStream,
    SPCT_SLEEP, SP_VISEME_4, DISPID_SVDisplayUI, DISPID_SRCERequestUI,
    DISPID_SDKCreateKey, DISPID_SRRGetXMLResult, SREHypothesis,
    SDKLCurrentConfig, DISPID_SRGDictationSetState,
    DISPID_SPRNumberOfElements, SAFTCCITT_ALaw_11kHzStereo,
    SpeechAddRemoveWord, SAFTDefault
)


class SpeechStreamSeekPositionType(IntFlag):
    SSSPTRelativeToStart = 0
    SSSPTRelativeToCurrentPosition = 1
    SSSPTRelativeToEnd = 2


class SpeechAudioState(IntFlag):
    SASClosed = 0
    SASStop = 1
    SASPause = 2
    SASRun = 3


class SpeechTokenContext(IntFlag):
    STCInprocServer = 1
    STCInprocHandler = 2
    STCLocalServer = 4
    STCRemoteServer = 16
    STCAll = 23


class SpeechTokenShellFolder(IntFlag):
    STSF_AppData = 26
    STSF_LocalAppData = 28
    STSF_CommonAppData = 35
    STSF_FlagCreate = 32768


class SpeechRunState(IntFlag):
    SRSEDone = 1
    SRSEIsSpeaking = 2


class DISPID_SpeechPhraseElement(IntFlag):
    DISPID_SPEAudioTimeOffset = 1
    DISPID_SPEAudioSizeTime = 2
    DISPID_SPEAudioStreamOffset = 3
    DISPID_SPEAudioSizeBytes = 4
    DISPID_SPERetainedStreamOffset = 5
    DISPID_SPERetainedSizeBytes = 6
    DISPID_SPEDisplayText = 7
    DISPID_SPELexicalForm = 8
    DISPID_SPEPronunciation = 9
    DISPID_SPEDisplayAttributes = 10
    DISPID_SPERequiredConfidence = 11
    DISPID_SPEActualConfidence = 12
    DISPID_SPEEngineConfidence = 13


class DISPID_SpeechVoiceEvent(IntFlag):
    DISPID_SVEStreamStart = 1
    DISPID_SVEStreamEnd = 2
    DISPID_SVEVoiceChange = 3
    DISPID_SVEBookmark = 4
    DISPID_SVEWord = 5
    DISPID_SVEPhoneme = 6
    DISPID_SVESentenceBoundary = 7
    DISPID_SVEViseme = 8
    DISPID_SVEAudioLevel = 9
    DISPID_SVEEnginePrivate = 10


class DISPID_SpeechPhraseElements(IntFlag):
    DISPID_SPEsCount = 1
    DISPID_SPEsItem = 0
    DISPID_SPEs_NewEnum = -4


class DISPID_SpeechPhraseReplacement(IntFlag):
    DISPID_SPRDisplayAttributes = 1
    DISPID_SPRText = 2
    DISPID_SPRFirstElement = 3
    DISPID_SPRNumberOfElements = 4


class DISPID_SpeechPhraseReplacements(IntFlag):
    DISPID_SPRsCount = 1
    DISPID_SPRsItem = 0
    DISPID_SPRs_NewEnum = -4


class SpeechBookmarkOptions(IntFlag):
    SBONone = 0
    SBOPause = 1


class SpeechVoiceEvents(IntFlag):
    SVEStartInputStream = 2
    SVEEndInputStream = 4
    SVEVoiceChange = 8
    SVEBookmark = 16
    SVEWordBoundary = 32
    SVEPhoneme = 64
    SVESentenceBoundary = 128
    SVEViseme = 256
    SVEAudioLevel = 512
    SVEPrivate = 32768
    SVEAllEvents = 33790


class DISPID_SpeechPhraseProperty(IntFlag):
    DISPID_SPPName = 1
    DISPID_SPPId = 2
    DISPID_SPPValue = 3
    DISPID_SPPFirstElement = 4
    DISPID_SPPNumberOfElements = 5
    DISPID_SPPEngineConfidence = 6
    DISPID_SPPConfidence = 7
    DISPID_SPPParent = 8
    DISPID_SPPChildren = 9


class SpeechEmulationCompareFlags(IntFlag):
    SECFIgnoreCase = 1
    SECFIgnoreKanaType = 65536
    SECFIgnoreWidth = 131072
    SECFNoSpecialChars = 536870912
    SECFEmulateResult = 1073741824
    SECFDefault = 196609


class DISPID_SpeechAudioBufferInfo(IntFlag):
    DISPID_SABIMinNotification = 1
    DISPID_SABIBufferSize = 2
    DISPID_SABIEventBias = 3


class DISPID_SpeechPhraseProperties(IntFlag):
    DISPID_SPPsCount = 1
    DISPID_SPPsItem = 0
    DISPID_SPPs_NewEnum = -4


class DISPID_SpeechPhraseRule(IntFlag):
    DISPID_SPRuleName = 1
    DISPID_SPRuleId = 2
    DISPID_SPRuleFirstElement = 3
    DISPID_SPRuleNumberOfElements = 4
    DISPID_SPRuleParent = 5
    DISPID_SPRuleChildren = 6
    DISPID_SPRuleConfidence = 7
    DISPID_SPRuleEngineConfidence = 8


class DISPID_SpeechAudioStatus(IntFlag):
    DISPID_SASFreeBufferSpace = 1
    DISPID_SASNonBlockingIO = 2
    DISPID_SASState = 3
    DISPID_SASCurrentSeekPosition = 4
    DISPID_SASCurrentDevicePosition = 5


class DISPID_SpeechCustomStream(IntFlag):
    DISPID_SCSBaseStream = 100


class DISPID_SpeechPhraseRules(IntFlag):
    DISPID_SPRulesCount = 1
    DISPID_SPRulesItem = 0
    DISPID_SPRules_NewEnum = -4


class DISPID_SpeechFileStream(IntFlag):
    DISPID_SFSOpen = 100
    DISPID_SFSClose = 101


class DISPID_SpeechMemoryStream(IntFlag):
    DISPID_SMSSetData = 100
    DISPID_SMSGetData = 101


class SpeechDisplayAttributes(IntFlag):
    SDA_No_Trailing_Space = 0
    SDA_One_Trailing_Space = 2
    SDA_Two_Trailing_Spaces = 4
    SDA_Consume_Leading_Spaces = 8


class DISPID_SpeechLexicon(IntFlag):
    DISPID_SLGenerationId = 1
    DISPID_SLGetWords = 2
    DISPID_SLAddPronunciation = 3
    DISPID_SLAddPronunciationByPhoneIds = 4
    DISPID_SLRemovePronunciation = 5
    DISPID_SLRemovePronunciationByPhoneIds = 6
    DISPID_SLGetPronunciations = 7
    DISPID_SLGetGenerationChange = 8


class SpeechVoicePriority(IntFlag):
    SVPNormal = 0
    SVPAlert = 1
    SVPOver = 2


class DISPID_SpeechRecognizer(IntFlag):
    DISPID_SRRecognizer = 1
    DISPID_SRAllowAudioInputFormatChangesOnNextSet = 2
    DISPID_SRAudioInput = 3
    DISPID_SRAudioInputStream = 4
    DISPID_SRIsShared = 5
    DISPID_SRState = 6
    DISPID_SRStatus = 7
    DISPID_SRProfile = 8
    DISPID_SREmulateRecognition = 9
    DISPID_SRCreateRecoContext = 10
    DISPID_SRGetFormat = 11
    DISPID_SRSetPropertyNumber = 12
    DISPID_SRGetPropertyNumber = 13
    DISPID_SRSetPropertyString = 14
    DISPID_SRGetPropertyString = 15
    DISPID_SRIsUISupported = 16
    DISPID_SRDisplayUI = 17
    DISPID_SRGetRecognizers = 18
    DISPID_SVGetAudioInputs = 19
    DISPID_SVGetProfiles = 20


class SpeechStreamFileMode(IntFlag):
    SSFMOpenForRead = 0
    SSFMOpenReadWrite = 1
    SSFMCreate = 2
    SSFMCreateForWrite = 3


class DISPID_SpeechLexiconWords(IntFlag):
    DISPID_SLWsCount = 1
    DISPID_SLWsItem = 0
    DISPID_SLWs_NewEnum = -4


class SpeechVisemeFeature(IntFlag):
    SVF_None = 0
    SVF_Stressed = 1
    SVF_Emphasis = 2


class SpeechVisemeType(IntFlag):
    SVP_0 = 0
    SVP_1 = 1
    SVP_2 = 2
    SVP_3 = 3
    SVP_4 = 4
    SVP_5 = 5
    SVP_6 = 6
    SVP_7 = 7
    SVP_8 = 8
    SVP_9 = 9
    SVP_10 = 10
    SVP_11 = 11
    SVP_12 = 12
    SVP_13 = 13
    SVP_14 = 14
    SVP_15 = 15
    SVP_16 = 16
    SVP_17 = 17
    SVP_18 = 18
    SVP_19 = 19
    SVP_20 = 20
    SVP_21 = 21


class DISPID_SpeechLexiconWord(IntFlag):
    DISPID_SLWLangId = 1
    DISPID_SLWType = 2
    DISPID_SLWWord = 3
    DISPID_SLWPronunciations = 4


class DISPID_SpeechLexiconProns(IntFlag):
    DISPID_SLPsCount = 1
    DISPID_SLPsItem = 0
    DISPID_SLPs_NewEnum = -4


class SpeechAudioFormatType(IntFlag):
    SAFTDefault = -1
    SAFTNoAssignedFormat = 0
    SAFTText = 1
    SAFTNonStandardFormat = 2
    SAFTExtendedAudioFormat = 3
    SAFT8kHz8BitMono = 4
    SAFT8kHz8BitStereo = 5
    SAFT8kHz16BitMono = 6
    SAFT8kHz16BitStereo = 7
    SAFT11kHz8BitMono = 8
    SAFT11kHz8BitStereo = 9
    SAFT11kHz16BitMono = 10
    SAFT11kHz16BitStereo = 11
    SAFT12kHz8BitMono = 12
    SAFT12kHz8BitStereo = 13
    SAFT12kHz16BitMono = 14
    SAFT12kHz16BitStereo = 15
    SAFT16kHz8BitMono = 16
    SAFT16kHz8BitStereo = 17
    SAFT16kHz16BitMono = 18
    SAFT16kHz16BitStereo = 19
    SAFT22kHz8BitMono = 20
    SAFT22kHz8BitStereo = 21
    SAFT22kHz16BitMono = 22
    SAFT22kHz16BitStereo = 23
    SAFT24kHz8BitMono = 24
    SAFT24kHz8BitStereo = 25
    SAFT24kHz16BitMono = 26
    SAFT24kHz16BitStereo = 27
    SAFT32kHz8BitMono = 28
    SAFT32kHz8BitStereo = 29
    SAFT32kHz16BitMono = 30
    SAFT32kHz16BitStereo = 31
    SAFT44kHz8BitMono = 32
    SAFT44kHz8BitStereo = 33
    SAFT44kHz16BitMono = 34
    SAFT44kHz16BitStereo = 35
    SAFT48kHz8BitMono = 36
    SAFT48kHz8BitStereo = 37
    SAFT48kHz16BitMono = 38
    SAFT48kHz16BitStereo = 39
    SAFTTrueSpeech_8kHz1BitMono = 40
    SAFTCCITT_ALaw_8kHzMono = 41
    SAFTCCITT_ALaw_8kHzStereo = 42
    SAFTCCITT_ALaw_11kHzMono = 43
    SAFTCCITT_ALaw_11kHzStereo = 44
    SAFTCCITT_ALaw_22kHzMono = 45
    SAFTCCITT_ALaw_22kHzStereo = 46
    SAFTCCITT_ALaw_44kHzMono = 47
    SAFTCCITT_ALaw_44kHzStereo = 48
    SAFTCCITT_uLaw_8kHzMono = 49
    SAFTCCITT_uLaw_8kHzStereo = 50
    SAFTCCITT_uLaw_11kHzMono = 51
    SAFTCCITT_uLaw_11kHzStereo = 52
    SAFTCCITT_uLaw_22kHzMono = 53
    SAFTCCITT_uLaw_22kHzStereo = 54
    SAFTCCITT_uLaw_44kHzMono = 55
    SAFTCCITT_uLaw_44kHzStereo = 56
    SAFTADPCM_8kHzMono = 57
    SAFTADPCM_8kHzStereo = 58
    SAFTADPCM_11kHzMono = 59
    SAFTADPCM_11kHzStereo = 60
    SAFTADPCM_22kHzMono = 61
    SAFTADPCM_22kHzStereo = 62
    SAFTADPCM_44kHzMono = 63
    SAFTADPCM_44kHzStereo = 64
    SAFTGSM610_8kHzMono = 65
    SAFTGSM610_11kHzMono = 66
    SAFTGSM610_22kHzMono = 67
    SAFTGSM610_44kHzMono = 68


class DISPID_SpeechLexiconPronunciation(IntFlag):
    DISPID_SLPType = 1
    DISPID_SLPLangId = 2
    DISPID_SLPPartOfSpeech = 3
    DISPID_SLPPhoneIds = 4
    DISPID_SLPSymbolic = 5


class SpeechVoiceSpeakFlags(IntFlag):
    SVSFDefault = 0
    SVSFlagsAsync = 1
    SVSFPurgeBeforeSpeak = 2
    SVSFIsFilename = 4
    SVSFIsXML = 8
    SVSFIsNotXML = 16
    SVSFPersistXML = 32
    SVSFNLPSpeakPunc = 64
    SVSFParseSapi = 128
    SVSFParseSsml = 256
    SVSFParseAutodetect = 0
    SVSFNLPMask = 64
    SVSFParseMask = 384
    SVSFVoiceMask = 511
    SVSFUnusedFlags = -512


class SpeechDiscardType(IntFlag):
    SDTProperty = 1
    SDTReplacement = 2
    SDTRule = 4
    SDTDisplayText = 8
    SDTLexicalForm = 16
    SDTPronunciation = 32
    SDTAudio = 64
    SDTAlternates = 128
    SDTAll = 255


class SpeechRecognitionType(IntFlag):
    SRTStandard = 0
    SRTAutopause = 1
    SRTEmulated = 2
    SRTSMLTimeout = 4
    SRTExtendableParse = 8
    SRTReSent = 16


class DISPID_SpeechVoice(IntFlag):
    DISPID_SVStatus = 1
    DISPID_SVVoice = 2
    DISPID_SVAudioOutput = 3
    DISPID_SVAudioOutputStream = 4
    DISPID_SVRate = 5
    DISPID_SVVolume = 6
    DISPID_SVAllowAudioOuputFormatChangesOnNextSet = 7
    DISPID_SVEventInterests = 8
    DISPID_SVPriority = 9
    DISPID_SVAlertBoundary = 10
    DISPID_SVSyncronousSpeakTimeout = 11
    DISPID_SVSpeak = 12
    DISPID_SVSpeakStream = 13
    DISPID_SVPause = 14
    DISPID_SVResume = 15
    DISPID_SVSkip = 16
    DISPID_SVGetVoices = 17
    DISPID_SVGetAudioOutputs = 18
    DISPID_SVWaitUntilDone = 19
    DISPID_SVSpeakCompleteEvent = 20
    DISPID_SVIsUISupported = 21
    DISPID_SVDisplayUI = 22


class DISPID_SpeechPhoneConverter(IntFlag):
    DISPID_SPCLangId = 1
    DISPID_SPCPhoneToId = 2
    DISPID_SPCIdToPhone = 3


class DISPID_SpeechRecoContextEvents(IntFlag):
    DISPID_SRCEStartStream = 1
    DISPID_SRCEEndStream = 2
    DISPID_SRCEBookmark = 3
    DISPID_SRCESoundStart = 4
    DISPID_SRCESoundEnd = 5
    DISPID_SRCEPhraseStart = 6
    DISPID_SRCERecognition = 7
    DISPID_SRCEHypothesis = 8
    DISPID_SRCEPropertyNumberChange = 9
    DISPID_SRCEPropertyStringChange = 10
    DISPID_SRCEFalseRecognition = 11
    DISPID_SRCEInterference = 12
    DISPID_SRCERequestUI = 13
    DISPID_SRCERecognizerStateChange = 14
    DISPID_SRCEAdaptation = 15
    DISPID_SRCERecognitionForOtherContext = 16
    DISPID_SRCEAudioLevel = 17
    DISPID_SRCEEnginePrivate = 18


class SpeechDataKeyLocation(IntFlag):
    SDKLDefaultLocation = 0
    SDKLCurrentUser = 1
    SDKLLocalMachine = 2
    SDKLCurrentConfig = 5


class SpeechLexiconType(IntFlag):
    SLTUser = 1
    SLTApp = 2


class SpeechPartOfSpeech(IntFlag):
    SPSNotOverriden = -1
    SPSUnknown = 0
    SPSNoun = 4096
    SPSVerb = 8192
    SPSModifier = 12288
    SPSFunction = 16384
    SPSInterjection = 20480
    SPSLMA = 28672
    SPSSuppressWord = 61440


class DISPID_SpeechWaveFormatEx(IntFlag):
    DISPID_SWFEFormatTag = 1
    DISPID_SWFEChannels = 2
    DISPID_SWFESamplesPerSec = 3
    DISPID_SWFEAvgBytesPerSec = 4
    DISPID_SWFEBlockAlign = 5
    DISPID_SWFEBitsPerSample = 6
    DISPID_SWFEExtraData = 7


class SpeechFormatType(IntFlag):
    SFTInput = 0
    SFTSREngine = 1


class DISPIDSPRG(IntFlag):
    DISPID_SRGId = 1
    DISPID_SRGRecoContext = 2
    DISPID_SRGState = 3
    DISPID_SRGRules = 4
    DISPID_SRGReset = 5
    DISPID_SRGCommit = 6
    DISPID_SRGCmdLoadFromFile = 7
    DISPID_SRGCmdLoadFromObject = 8
    DISPID_SRGCmdLoadFromResource = 9
    DISPID_SRGCmdLoadFromMemory = 10
    DISPID_SRGCmdLoadFromProprietaryGrammar = 11
    DISPID_SRGCmdSetRuleState = 12
    DISPID_SRGCmdSetRuleIdState = 13
    DISPID_SRGDictationLoad = 14
    DISPID_SRGDictationUnload = 15
    DISPID_SRGDictationSetState = 16
    DISPID_SRGSetWordSequenceData = 17
    DISPID_SRGSetTextSelection = 18
    DISPID_SRGIsPronounceable = 19


class SPDATAKEYLOCATION(IntFlag):
    SPDKL_DefaultLocation = 0
    SPDKL_CurrentUser = 1
    SPDKL_LocalMachine = 2
    SPDKL_CurrentConfig = 5


class DISPID_SpeechVoiceStatus(IntFlag):
    DISPID_SVSCurrentStreamNumber = 1
    DISPID_SVSLastStreamNumberQueued = 2
    DISPID_SVSLastResult = 3
    DISPID_SVSRunningState = 4
    DISPID_SVSInputWordPosition = 5
    DISPID_SVSInputWordLength = 6
    DISPID_SVSInputSentencePosition = 7
    DISPID_SVSInputSentenceLength = 8
    DISPID_SVSLastBookmark = 9
    DISPID_SVSLastBookmarkId = 10
    DISPID_SVSPhonemeId = 11
    DISPID_SVSVisemeId = 12


class DISPID_SpeechRecoContext(IntFlag):
    DISPID_SRCRecognizer = 1
    DISPID_SRCAudioInInterferenceStatus = 2
    DISPID_SRCRequestedUIType = 3
    DISPID_SRCVoice = 4
    DISPID_SRAllowVoiceFormatMatchingOnNextSet = 5
    DISPID_SRCVoicePurgeEvent = 6
    DISPID_SRCEventInterests = 7
    DISPID_SRCCmdMaxAlternates = 8
    DISPID_SRCState = 9
    DISPID_SRCRetainedAudio = 10
    DISPID_SRCRetainedAudioFormat = 11
    DISPID_SRCPause = 12
    DISPID_SRCResume = 13
    DISPID_SRCCreateGrammar = 14
    DISPID_SRCCreateResultFromMemory = 15
    DISPID_SRCBookmark = 16
    DISPID_SRCSetAdaptationData = 17


class DISPID_SpeechRecognizerStatus(IntFlag):
    DISPID_SRSAudioStatus = 1
    DISPID_SRSCurrentStreamPosition = 2
    DISPID_SRSCurrentStreamNumber = 3
    DISPID_SRSNumberOfActiveRules = 4
    DISPID_SRSClsidEngine = 5
    DISPID_SRSSupportedLanguages = 6


class SPXMLRESULTOPTIONS(IntFlag):
    SPXRO_SML = 0
    SPXRO_Alternates_SML = 1


class SPLEXICONTYPE(IntFlag):
    eLEXTYPE_USER = 1
    eLEXTYPE_APP = 2
    eLEXTYPE_VENDORLEXICON = 4
    eLEXTYPE_LETTERTOSOUND = 8
    eLEXTYPE_MORPHOLOGY = 16
    eLEXTYPE_RESERVED4 = 32
    eLEXTYPE_USER_SHORTCUT = 64
    eLEXTYPE_RESERVED6 = 128
    eLEXTYPE_RESERVED7 = 256
    eLEXTYPE_RESERVED8 = 512
    eLEXTYPE_RESERVED9 = 1024
    eLEXTYPE_RESERVED10 = 2048
    eLEXTYPE_PRIVATE1 = 4096
    eLEXTYPE_PRIVATE2 = 8192
    eLEXTYPE_PRIVATE3 = 16384
    eLEXTYPE_PRIVATE4 = 32768
    eLEXTYPE_PRIVATE5 = 65536
    eLEXTYPE_PRIVATE6 = 131072
    eLEXTYPE_PRIVATE7 = 262144
    eLEXTYPE_PRIVATE8 = 524288
    eLEXTYPE_PRIVATE9 = 1048576
    eLEXTYPE_PRIVATE10 = 2097152
    eLEXTYPE_PRIVATE11 = 4194304
    eLEXTYPE_PRIVATE12 = 8388608
    eLEXTYPE_PRIVATE13 = 16777216
    eLEXTYPE_PRIVATE14 = 33554432
    eLEXTYPE_PRIVATE15 = 67108864
    eLEXTYPE_PRIVATE16 = 134217728
    eLEXTYPE_PRIVATE17 = 268435456
    eLEXTYPE_PRIVATE18 = 536870912
    eLEXTYPE_PRIVATE19 = 1073741824
    eLEXTYPE_PRIVATE20 = -2147483648


class SPPARTOFSPEECH(IntFlag):
    SPPS_NotOverriden = -1
    SPPS_Unknown = 0
    SPPS_Noun = 4096
    SPPS_Verb = 8192
    SPPS_Modifier = 12288
    SPPS_Function = 16384
    SPPS_Interjection = 20480
    SPPS_Noncontent = 24576
    SPPS_LMA = 28672
    SPPS_SuppressWord = 61440


class DISPID_SpeechDataKey(IntFlag):
    DISPID_SDKSetBinaryValue = 1
    DISPID_SDKGetBinaryValue = 2
    DISPID_SDKSetStringValue = 3
    DISPID_SDKGetStringValue = 4
    DISPID_SDKSetLongValue = 5
    DISPID_SDKGetlongValue = 6
    DISPID_SDKOpenKey = 7
    DISPID_SDKCreateKey = 8
    DISPID_SDKDeleteKey = 9
    DISPID_SDKDeleteValue = 10
    DISPID_SDKEnumKeys = 11
    DISPID_SDKEnumValues = 12


class SPGRAMMARSTATE(IntFlag):
    SPGS_DISABLED = 0
    SPGS_ENABLED = 1
    SPGS_EXCLUSIVE = 3


class SPLOADOPTIONS(IntFlag):
    SPLO_STATIC = 0
    SPLO_DYNAMIC = 1


class SPVPRIORITY(IntFlag):
    SPVPRI_NORMAL = 0
    SPVPRI_ALERT = 1
    SPVPRI_OVER = 2


class SpeechRetainedAudioOptions(IntFlag):
    SRAONone = 0
    SRAORetainAudio = 1


class SPINTERFERENCE(IntFlag):
    SPINTERFERENCE_NONE = 0
    SPINTERFERENCE_NOISE = 1
    SPINTERFERENCE_NOSIGNAL = 2
    SPINTERFERENCE_TOOLOUD = 3
    SPINTERFERENCE_TOOQUIET = 4
    SPINTERFERENCE_TOOFAST = 5
    SPINTERFERENCE_TOOSLOW = 6
    SPINTERFERENCE_LATENCY_WARNING = 7
    SPINTERFERENCE_LATENCY_TRUNCATE_BEGIN = 8
    SPINTERFERENCE_LATENCY_TRUNCATE_END = 9


class SPEVENTENUM(IntFlag):
    SPEI_UNDEFINED = 0
    SPEI_START_INPUT_STREAM = 1
    SPEI_END_INPUT_STREAM = 2
    SPEI_VOICE_CHANGE = 3
    SPEI_TTS_BOOKMARK = 4
    SPEI_WORD_BOUNDARY = 5
    SPEI_PHONEME = 6
    SPEI_SENTENCE_BOUNDARY = 7
    SPEI_VISEME = 8
    SPEI_TTS_AUDIO_LEVEL = 9
    SPEI_TTS_PRIVATE = 15
    SPEI_MIN_TTS = 1
    SPEI_MAX_TTS = 15
    SPEI_END_SR_STREAM = 34
    SPEI_SOUND_START = 35
    SPEI_SOUND_END = 36
    SPEI_PHRASE_START = 37
    SPEI_RECOGNITION = 38
    SPEI_HYPOTHESIS = 39
    SPEI_SR_BOOKMARK = 40
    SPEI_PROPERTY_NUM_CHANGE = 41
    SPEI_PROPERTY_STRING_CHANGE = 42
    SPEI_FALSE_RECOGNITION = 43
    SPEI_INTERFERENCE = 44
    SPEI_REQUEST_UI = 45
    SPEI_RECO_STATE_CHANGE = 46
    SPEI_ADAPTATION = 47
    SPEI_START_SR_STREAM = 48
    SPEI_RECO_OTHER_CONTEXT = 49
    SPEI_SR_AUDIO_LEVEL = 50
    SPEI_SR_RETAINEDAUDIO = 51
    SPEI_SR_PRIVATE = 52
    SPEI_ACTIVE_CATEGORY_CHANGED = 53
    SPEI_RESERVED5 = 54
    SPEI_RESERVED6 = 55
    SPEI_MIN_SR = 34
    SPEI_MAX_SR = 55
    SPEI_RESERVED1 = 30
    SPEI_RESERVED2 = 33
    SPEI_RESERVED3 = 63


class SpeechGrammarRuleStateTransitionType(IntFlag):
    SGRSTTEpsilon = 0
    SGRSTTWord = 1
    SGRSTTRule = 2
    SGRSTTDictation = 3
    SGRSTTWildcard = 4
    SGRSTTTextBuffer = 5


class SpeechGrammarWordType(IntFlag):
    SGDisplay = 0
    SGLexical = 1
    SGPronounciation = 2
    SGLexicalNoSpecialChars = 3


class SpeechRecognizerState(IntFlag):
    SRSInactive = 0
    SRSActive = 1
    SRSActiveAlways = 2
    SRSInactiveWithPurge = 3


class DISPID_SpeechGrammarRules(IntFlag):
    DISPID_SGRsCount = 1
    DISPID_SGRsDynamic = 2
    DISPID_SGRsAdd = 3
    DISPID_SGRsCommit = 4
    DISPID_SGRsCommitAndSave = 5
    DISPID_SGRsFindRule = 6
    DISPID_SGRsItem = 0
    DISPID_SGRs_NewEnum = -4


class DISPID_SpeechGrammarRuleState(IntFlag):
    DISPID_SGRSRule = 1
    DISPID_SGRSTransitions = 2
    DISPID_SGRSAddWordTransition = 3
    DISPID_SGRSAddRuleTransition = 4
    DISPID_SGRSAddSpecialTransition = 5


class _SPAUDIOSTATE(IntFlag):
    SPAS_CLOSED = 0
    SPAS_STOP = 1
    SPAS_PAUSE = 2
    SPAS_RUN = 3


class DISPID_SpeechRecoResult2(IntFlag):
    DISPID_SRRSetTextFeedback = 12


class SpeechRuleState(IntFlag):
    SGDSInactive = 0
    SGDSActive = 1
    SGDSActiveWithAutoPause = 3
    SGDSActiveUserDelimited = 4


class SpeechEngineConfidence(IntFlag):
    SECLowConfidence = -1
    SECNormalConfidence = 0
    SECHighConfidence = 1


class SPAUDIOOPTIONS(IntFlag):
    SPAO_NONE = 0
    SPAO_RETAIN_AUDIO = 1


class DISPID_SpeechObjectTokens(IntFlag):
    DISPID_SOTsCount = 1
    DISPID_SOTsItem = 0
    DISPID_SOTs_NewEnum = -4


class SPADAPTATIONRELEVANCE(IntFlag):
    SPAR_Unknown = 0
    SPAR_Low = 1
    SPAR_Medium = 2
    SPAR_High = 3


class SpeechSpecialTransitionType(IntFlag):
    SSTTWildcard = 1
    SSTTDictation = 2
    SSTTTextBuffer = 3


class SpeechInterference(IntFlag):
    SINone = 0
    SINoise = 1
    SINoSignal = 2
    SITooLoud = 3
    SITooQuiet = 4
    SITooFast = 5
    SITooSlow = 6


class DISPID_SpeechGrammarRuleStateTransitions(IntFlag):
    DISPID_SGRSTsCount = 1
    DISPID_SGRSTsItem = 0
    DISPID_SGRSTs_NewEnum = -4


class SpeechWordType(IntFlag):
    SWTAdded = 1
    SWTDeleted = 2


class DISPID_SpeechObjectTokenCategory(IntFlag):
    DISPID_SOTCId = 1
    DISPID_SOTCDefault = 2
    DISPID_SOTCSetId = 3
    DISPID_SOTCGetDataKey = 4
    DISPID_SOTCEnumerateTokens = 5


class SPWORDTYPE(IntFlag):
    eWORDTYPE_ADDED = 1
    eWORDTYPE_DELETED = 2


class SPBOOKMARKOPTIONS(IntFlag):
    SPBO_NONE = 0
    SPBO_PAUSE = 1
    SPBO_AHEAD = 2
    SPBO_TIME_UNITS = 4


class SPCONTEXTSTATE(IntFlag):
    SPCS_DISABLED = 0
    SPCS_ENABLED = 1


class DISPID_SpeechGrammarRule(IntFlag):
    DISPID_SGRAttributes = 1
    DISPID_SGRInitialState = 2
    DISPID_SGRName = 3
    DISPID_SGRId = 4
    DISPID_SGRClear = 5
    DISPID_SGRAddResource = 6
    DISPID_SGRAddState = 7


class SPRECOSTATE(IntFlag):
    SPRST_INACTIVE = 0
    SPRST_ACTIVE = 1
    SPRST_ACTIVE_ALWAYS = 2
    SPRST_INACTIVE_WITH_PURGE = 3
    SPRST_NUM_STATES = 4


class SPWAVEFORMATTYPE(IntFlag):
    SPWF_INPUT = 0
    SPWF_SRENGINE = 1


class SPSEMANTICFORMAT(IntFlag):
    SPSMF_SAPI_PROPERTIES = 0
    SPSMF_SRGS_SEMANTICINTERPRETATION_MS = 1
    SPSMF_SRGS_SAPIPROPERTIES = 2
    SPSMF_UPS = 4
    SPSMF_SRGS_SEMANTICINTERPRETATION_W3C = 8


class DISPID_SpeechPhraseBuilder(IntFlag):
    DISPID_SPPBRestorePhraseFromMemory = 1


class SpeechLoadOption(IntFlag):
    SLOStatic = 0
    SLODynamic = 1


class DISPID_SpeechRecoResultTimes(IntFlag):
    DISPID_SRRTStreamTime = 1
    DISPID_SRRTLength = 2
    DISPID_SRRTTickCount = 3
    DISPID_SRRTOffsetFromStart = 4


class SPSHORTCUTTYPE(IntFlag):
    SPSHT_NotOverriden = -1
    SPSHT_Unknown = 0
    SPSHT_EMAIL = 4096
    SPSHT_OTHER = 8192
    SPPS_RESERVED1 = 12288
    SPPS_RESERVED2 = 16384
    SPPS_RESERVED3 = 20480
    SPPS_RESERVED4 = 61440


class SPFILEMODE(IntFlag):
    SPFM_OPEN_READONLY = 0
    SPFM_OPEN_READWRITE = 1
    SPFM_CREATE = 2
    SPFM_CREATE_ALWAYS = 3
    SPFM_NUM_MODES = 4


class SPGRAMMARWORDTYPE(IntFlag):
    SPWT_DISPLAY = 0
    SPWT_LEXICAL = 1
    SPWT_PRONUNCIATION = 2
    SPWT_LEXICAL_NO_SPECIAL_CHARS = 3


class DISPID_SpeechPhraseAlternate(IntFlag):
    DISPID_SPARecoResult = 1
    DISPID_SPAStartElementInResult = 2
    DISPID_SPANumberOfElementsInResult = 3
    DISPID_SPAPhraseInfo = 4
    DISPID_SPACommit = 5


class DISPID_SpeechPhraseAlternates(IntFlag):
    DISPID_SPAsCount = 1
    DISPID_SPAsItem = 0
    DISPID_SPAs_NewEnum = -4


class DISPID_SpeechPhraseInfo(IntFlag):
    DISPID_SPILanguageId = 1
    DISPID_SPIGrammarId = 2
    DISPID_SPIStartTime = 3
    DISPID_SPIAudioStreamPosition = 4
    DISPID_SPIAudioSizeBytes = 5
    DISPID_SPIRetainedSizeBytes = 6
    DISPID_SPIAudioSizeTime = 7
    DISPID_SPIRule = 8
    DISPID_SPIProperties = 9
    DISPID_SPIElements = 10
    DISPID_SPIReplacements = 11
    DISPID_SPIEngineId = 12
    DISPID_SPIEnginePrivateData = 13
    DISPID_SPISaveToMemory = 14
    DISPID_SPIGetText = 15
    DISPID_SPIGetDisplayAttributes = 16


class SPCATEGORYTYPE(IntFlag):
    SPCT_COMMAND = 0
    SPCT_DICTATION = 1
    SPCT_SLEEP = 2
    SPCT_SUB_COMMAND = 3
    SPCT_SUB_DICTATION = 4


class DISPID_SpeechObjectToken(IntFlag):
    DISPID_SOTId = 1
    DISPID_SOTDataKey = 2
    DISPID_SOTCategory = 3
    DISPID_SOTGetDescription = 4
    DISPID_SOTSetId = 5
    DISPID_SOTGetAttribute = 6
    DISPID_SOTCreateInstance = 7
    DISPID_SOTRemove = 8
    DISPID_SOTGetStorageFileName = 9
    DISPID_SOTRemoveStorageFileName = 10
    DISPID_SOTIsUISupported = 11
    DISPID_SOTDisplayUI = 12
    DISPID_SOTMatchesAttributes = 13


class SpeechRecoContextState(IntFlag):
    SRCS_Disabled = 0
    SRCS_Enabled = 1


class SPVISEMES(IntFlag):
    SP_VISEME_0 = 0
    SP_VISEME_1 = 1
    SP_VISEME_2 = 2
    SP_VISEME_3 = 3
    SP_VISEME_4 = 4
    SP_VISEME_5 = 5
    SP_VISEME_6 = 6
    SP_VISEME_7 = 7
    SP_VISEME_8 = 8
    SP_VISEME_9 = 9
    SP_VISEME_10 = 10
    SP_VISEME_11 = 11
    SP_VISEME_12 = 12
    SP_VISEME_13 = 13
    SP_VISEME_14 = 14
    SP_VISEME_15 = 15
    SP_VISEME_16 = 16
    SP_VISEME_17 = 17
    SP_VISEME_18 = 18
    SP_VISEME_19 = 19
    SP_VISEME_20 = 20
    SP_VISEME_21 = 21


class SpeechRecoEvents(IntFlag):
    SREStreamEnd = 1
    SRESoundStart = 2
    SRESoundEnd = 4
    SREPhraseStart = 8
    SRERecognition = 16
    SREHypothesis = 32
    SREBookmark = 64
    SREPropertyNumChange = 128
    SREPropertyStringChange = 256
    SREFalseRecognition = 512
    SREInterference = 1024
    SRERequestUI = 2048
    SREStateChange = 4096
    SREAdaptation = 8192
    SREStreamStart = 16384
    SRERecoOtherContext = 32768
    SREAudioLevel = 65536
    SREPrivate = 262144
    SREAllEvents = 393215


class DISPID_SpeechAudioFormat(IntFlag):
    DISPID_SAFType = 1
    DISPID_SAFGuid = 2
    DISPID_SAFGetWaveFormatEx = 3
    DISPID_SAFSetWaveFormatEx = 4


class SpeechWordPronounceable(IntFlag):
    SWPUnknownWordUnpronounceable = 0
    SWPUnknownWordPronounceable = 1
    SWPKnownWordPronounceable = 2


class DISPID_SpeechBaseStream(IntFlag):
    DISPID_SBSFormat = 1
    DISPID_SBSRead = 2
    DISPID_SBSWrite = 3
    DISPID_SBSSeek = 4


class DISPID_SpeechGrammarRuleStateTransition(IntFlag):
    DISPID_SGRSTType = 1
    DISPID_SGRSTText = 2
    DISPID_SGRSTRule = 3
    DISPID_SGRSTWeight = 4
    DISPID_SGRSTPropertyName = 5
    DISPID_SGRSTPropertyId = 6
    DISPID_SGRSTPropertyValue = 7
    DISPID_SGRSTNextState = 8


class SPRULESTATE(IntFlag):
    SPRS_INACTIVE = 0
    SPRS_ACTIVE = 1
    SPRS_ACTIVE_WITH_AUTO_PAUSE = 3
    SPRS_ACTIVE_USER_DELIMITED = 4


class SPWORDPRONOUNCEABLE(IntFlag):
    SPWP_UNKNOWN_WORD_UNPRONOUNCEABLE = 0
    SPWP_UNKNOWN_WORD_PRONOUNCEABLE = 1
    SPWP_KNOWN_WORD_PRONOUNCEABLE = 2


class SpeechGrammarState(IntFlag):
    SGSEnabled = 1
    SGSDisabled = 0
    SGSExclusive = 3


class SpeechRuleAttributes(IntFlag):
    SRATopLevel = 1
    SRADefaultToActive = 2
    SRAExport = 4
    SRAImport = 8
    SRAInterpreter = 16
    SRADynamic = 32
    SRARoot = 64


class DISPIDSPTSI(IntFlag):
    DISPIDSPTSI_ActiveOffset = 1
    DISPIDSPTSI_ActiveLength = 2
    DISPIDSPTSI_SelectionOffset = 3
    DISPIDSPTSI_SelectionLength = 4


class DISPID_SpeechAudio(IntFlag):
    DISPID_SAStatus = 200
    DISPID_SABufferInfo = 201
    DISPID_SADefaultFormat = 202
    DISPID_SAVolume = 203
    DISPID_SABufferNotifySize = 204
    DISPID_SAEventHandle = 205
    DISPID_SASetState = 206


class DISPID_SpeechMMSysAudio(IntFlag):
    DISPID_SMSADeviceId = 300
    DISPID_SMSALineId = 301
    DISPID_SMSAMMHandle = 302


class DISPID_SpeechRecoResult(IntFlag):
    DISPID_SRRRecoContext = 1
    DISPID_SRRTimes = 2
    DISPID_SRRAudioFormat = 3
    DISPID_SRRPhraseInfo = 4
    DISPID_SRRAlternates = 5
    DISPID_SRRAudio = 6
    DISPID_SRRSpeakAudio = 7
    DISPID_SRRSaveToMemory = 8
    DISPID_SRRDiscardResultInfo = 9


class DISPID_SpeechXMLRecoResult(IntFlag):
    DISPID_SRRGetXMLResult = 10
    DISPID_SRRGetXMLErrorInfo = 11


SPAUDIOSTATE = _SPAUDIOSTATE
SPSTREAMFORMATTYPE = SPWAVEFORMATTYPE


__all__ = [
    'SVPOver', 'DISPID_SVSRunningState', '_ISpeechRecoContextEvents',
    'SPTEXTSELECTIONINFO', 'SpeechDiscardType', 'eLEXTYPE_PRIVATE15',
    'SAFTGSM610_11kHzMono', 'STCAll', 'eLEXTYPE_PRIVATE5',
    'DISPID_SPPBRestorePhraseFromMemory', 'SPEI_MIN_TTS',
    'SVSFParseMask', 'SPRS_INACTIVE', 'DISPID_SRGCmdLoadFromFile',
    'SREAudioLevel', 'SPAO_RETAIN_AUDIO', 'SGSDisabled',
    'DISPID_SOTIsUISupported', 'DISPIDSPTSI_SelectionLength',
    'SVSFPersistXML', 'SpeechVisemeType', 'ISpRecognizer2',
    'SpAudioFormat', 'DISPID_SOTCategory', 'SpeechVisemeFeature',
    'SAFT8kHz8BitMono', 'SPINTERFERENCE_LATENCY_TRUNCATE_END',
    'DISPID_SpeechPhraseInfo', 'SpNullPhoneConverter',
    'DISPID_SpeechRecognizer', 'DISPID_SRCRequestedUIType',
    'SPDATAKEYLOCATION', 'DISPID_SRCState',
    'SPSMF_SRGS_SAPIPROPERTIES', 'SpMMAudioOut',
    'DISPID_SPERequiredConfidence', 'SpeechPartOfSpeech',
    'DISPID_SDKGetlongValue', 'UINT_PTR', 'SPGS_DISABLED',
    'ISpeechGrammarRuleState', 'DISPID_SRRAlternates',
    'SpeechDataKeyLocation', 'DISPID_SPPChildren',
    'SpeechPropertyAdaptationOn', 'SpeechVoicePriority',
    'SWPUnknownWordUnpronounceable', 'DISPID_SMSADeviceId',
    'ISpEventSink', 'SPPS_Modifier', 'SDTRule', 'SP_VISEME_19',
    'SRSInactive', 'SDKLDefaultLocation', 'SSSPTRelativeToEnd',
    'SpMMAudioIn', 'SPXRO_Alternates_SML', 'SAFTCCITT_ALaw_22kHzMono',
    'SPVOICESTATUS', 'SP_VISEME_10', 'SAFTCCITT_ALaw_44kHzMono',
    'SPRECOSTATE', 'DISPID_SRCERecognitionForOtherContext',
    'SPEI_TTS_BOOKMARK', 'ISpeechAudio',
    'DISPID_SVAllowAudioOuputFormatChangesOnNextSet',
    'SWPKnownWordPronounceable', 'SVP_16', 'DISPID_SRGRules',
    'DISPID_SRCPause', 'SPBINARYGRAMMAR',
    'DISPID_SGRSAddWordTransition', 'SPFILEMODE', 'SFTSREngine',
    'ISpStreamFormatConverter', 'SPWORDPRONUNCIATIONLIST',
    'SpeechAudioVolume', 'SpCustomStream', 'SPVISEMES',
    'SGRSTTWildcard', 'DISPID_SVSpeakStream', 'eLEXTYPE_RESERVED4',
    'SAFTCCITT_uLaw_11kHzMono', 'SpeechRunState',
    'SPINTERFERENCE_NOISE', 'SPRS_ACTIVE', 'eLEXTYPE_PRIVATE17',
    'SPSMF_UPS', 'DISPID_SGRSTRule', 'SPEI_SR_AUDIO_LEVEL',
    'SRATopLevel', 'DISPID_SRGetRecognizers',
    'ISpeechRecognizerStatus', 'SVEAudioLevel',
    'SpeechDisplayAttributes', 'SPEI_UNDEFINED', 'SPGS_EXCLUSIVE',
    'DISPID_SPRuleEngineConfidence', 'SPXRO_SML',
    'DISPID_SGRsCommitAndSave', 'ISpRecoContext2',
    '__MIDL_IWinTypes_0009', 'SAFT16kHz8BitMono', 'SDTAll', 'SBONone',
    'DISPID_SPRs_NewEnum', 'ISpeechMemoryStream', 'SAFT11kHz8BitMono',
    'DISPID_SRCEAudioLevel', 'ISpEventSource', 'SPEI_END_SR_STREAM',
    'SPADAPTATIONRELEVANCE', 'SPWT_DISPLAY',
    'SPRST_INACTIVE_WITH_PURGE', 'ISpRecognizer3', 'SPPS_Function',
    'SRAImport', 'DISPID_SPRsCount', 'DISPID_SPERetainedStreamOffset',
    'SPDKL_LocalMachine', 'SAFTCCITT_uLaw_22kHzStereo',
    'SPEI_START_SR_STREAM', 'SPEI_RESERVED6',
    'DISPID_SpeechPhraseProperties', 'DISPID_SDKOpenKey',
    'SPEI_TTS_PRIVATE', 'DISPID_SRGIsPronounceable',
    'ISpeechPhraseReplacements', 'DISPID_SRRTStreamTime',
    'SPEI_SOUND_START', 'SGDSActiveUserDelimited',
    'SPWT_PRONUNCIATION', 'SAFT32kHz8BitMono', 'SPSHORTCUTPAIRLIST',
    'ISpeechRecoResult', 'DISPID_SMSSetData', 'SAFT32kHz8BitStereo',
    'DISPID_SVStatus', 'SRSActive', 'SP_VISEME_21',
    'SPRS_ACTIVE_WITH_AUTO_PAUSE', 'DISPID_SPIElements',
    'DISPID_SAEventHandle', 'SAFTADPCM_22kHzMono',
    'DISPID_SRSCurrentStreamNumber', 'SREFalseRecognition',
    'DISPID_SpeechPhraseElements', 'ISpDataKey',
    'DISPID_SRCEHypothesis', 'SpeechAudioProperties',
    'SECFIgnoreWidth', 'DISPID_SPIGrammarId',
    'eLEXTYPE_VENDORLEXICON', 'DISPID_SWFEAvgBytesPerSec',
    'DISPID_SRSAudioStatus', 'DISPID_SpeechLexiconWords',
    'SP_VISEME_12', 'DISPID_SABufferNotifySize',
    'SVSFPurgeBeforeSpeak', 'eLEXTYPE_LETTERTOSOUND',
    'DISPID_SVGetProfiles', 'ISpeechPhraseElement', 'SP_VISEME_2',
    'SVEEndInputStream', 'DISPID_SDKEnumKeys', 'SPEI_MAX_SR',
    'eLEXTYPE_RESERVED9', 'SVP_13', 'SVP_3', 'SPPS_SuppressWord',
    'SPEI_WORD_BOUNDARY', 'SPCS_ENABLED', 'SPRST_INACTIVE', 'SLTUser',
    'DISPID_SLPsItem', 'ISpNotifySink', 'DISPID_SRCEEnginePrivate',
    'DISPID_SGRsItem', 'SVEAllEvents', 'SPWF_SRENGINE',
    'SPPS_Unknown', 'DISPID_SGRSTText', 'SPINTERFERENCE_TOOSLOW',
    'SPSHT_OTHER', 'ISpRecoCategory', 'DISPID_SREmulateRecognition',
    'DISPID_SVPause', 'SGRSTTDictation', 'DISPID_SRRSetTextFeedback',
    'DISPID_SLWs_NewEnum', 'DISPID_SpeechLexiconWord',
    'ISpNotifySource', 'SVP_5', 'SPAUDIOSTATE',
    'DISPID_SPPConfidence', 'SPEI_VISEME', 'SpeechMicTraining',
    'SPPS_Interjection', 'SPFM_OPEN_READWRITE', 'SpeechLoadOption',
    'DISPID_SRGDictationUnload', 'ISpeechPhraseInfoBuilder',
    'SDKLCurrentUser', 'DISPID_SGRAttributes', 'SVP_12',
    'SPLO_STATIC', 'SVEPhoneme', 'DISPID_SOTs_NewEnum',
    'eLEXTYPE_PRIVATE12', 'DISPID_SVSLastBookmark', 'SPSSuppressWord',
    'DISPID_SDKGetBinaryValue',
    'DISPID_SRAllowVoiceFormatMatchingOnNextSet', 'ISpSerializeState',
    'DISPID_SPPFirstElement', 'SAFT24kHz8BitStereo',
    'ISpeechObjectTokenCategory', 'SPINTERFERENCE_NONE',
    'DISPID_SDKGetStringValue', 'ISpMMSysAudio', 'DISPID_SVSkip',
    'eLEXTYPE_PRIVATE7', 'SpeechCategoryAppLexicons', 'SWTDeleted',
    'DISPID_SGRsFindRule', 'SITooFast', 'SWTAdded',
    'SpeechPropertyNormalConfidenceThreshold', 'SPPHRASERULE',
    'SRSEDone', 'DISPID_SRGCmdLoadFromResource', 'SpSharedRecognizer',
    'SpObjectToken', 'DISPID_SRSSupportedLanguages',
    'DISPID_SPARecoResult', 'DISPID_SPEsCount', 'DISPID_SGRSTType',
    'DISPID_SpeechPhoneConverter', 'SRCS_Enabled',
    'DISPID_SPEEngineConfidence', 'SPDKL_CurrentConfig',
    'DISPID_SGRSTransitions', 'SVP_17', 'DISPID_SpeechObjectToken',
    'DISPID_SASCurrentSeekPosition', 'WAVEFORMATEX', 'DISPID_SPPName',
    'SPWORDPRONOUNCEABLE', 'SVF_None', 'SPBO_AHEAD', 'SPVPRI_NORMAL',
    'SpeechEngineConfidence', 'ISpPhoneticAlphabetSelection',
    'DISPID_SPAPhraseInfo', 'SGRSTTEpsilon', 'SRESoundEnd',
    'SRERecognition', 'SGSExclusive', 'SRTExtendableParse',
    'DISPID_SRRPhraseInfo', 'SSFMCreateForWrite', 'ISpStreamFormat',
    'SPEI_HYPOTHESIS', 'DISPID_SPRulesItem', 'DISPID_SpeechLexicon',
    'SpeechRuleState', 'SP_VISEME_16', 'SPWORDPRONUNCIATION',
    'SpWaveFormatEx', 'ISpeechRecoResultDispatch',
    'DISPID_SLWPronunciations', 'DISPID_SLGetGenerationChange',
    'SpPhraseInfoBuilder', 'DISPIDSPTSI', 'DISPID_SPRFirstElement',
    'DISPID_SVSVisemeId', 'SINoSignal', 'DISPID_SRCCmdMaxAlternates',
    'DISPID_SOTDataKey', 'DISPID_SLPs_NewEnum',
    'DISPID_SVAudioOutput', 'DISPID_SLAddPronunciationByPhoneIds',
    'SPEI_RECO_STATE_CHANGE', 'SPSTREAMFORMATTYPE', 'SREPrivate',
    'SDA_No_Trailing_Space', 'DISPID_SpeechXMLRecoResult',
    'DISPID_SPEActualConfidence', 'ISpObjectToken',
    'DISPID_SPIProperties', 'DISPID_SpeechLexiconProns',
    'SPAUDIOSTATUS', 'SDTProperty', 'SVP_4', 'eLEXTYPE_PRIVATE6',
    'SP_VISEME_0', 'DISPID_SRIsShared', 'SpeechGrammarTagWildcard',
    'SpeechTokenKeyAttributes', 'IStream', 'DISPID_SRGetFormat',
    'SPGRAMMARSTATE', 'ISpeechRecoResultTimes',
    'SpeechSpecialTransitionType', 'SPBOOKMARKOPTIONS',
    'DISPID_SRGId', 'SPRS_ACTIVE_USER_DELIMITED', 'SREAllEvents',
    'SpPhoneConverter', 'eLEXTYPE_PRIVATE4',
    'SpeechCategoryRecognizers', 'DISPID_SOTCEnumerateTokens',
    'DISPID_SPRules_NewEnum', 'STCRemoteServer', 'SVP_18',
    'SVF_Emphasis', 'DISPID_SGRSTsItem', 'DISPID_SRGDictationLoad',
    'SPWAVEFORMATTYPE', 'SSSPTRelativeToCurrentPosition',
    'SpeechTokenContext', 'DISPID_SVSLastResult',
    'DISPID_SRCERecognizerStateChange', 'SpeechRecognitionType',
    'DISPID_SRRTTickCount', 'SRAInterpreter', 'DISPID_SLWLangId',
    'SVEViseme', 'DISPID_SPPs_NewEnum', 'SVSFVoiceMask',
    'DISPID_SRGCommit', 'SPEVENT', 'SpeechRecoProfileProperties',
    'SpeechGrammarTagUnlimitedDictation', 'SpeechEngineProperties',
    'SAFTADPCM_8kHzStereo', 'DISPID_SABIMinNotification',
    'DISPID_SPIStartTime', 'SpeechGrammarState',
    'SpeechWordPronounceable', 'DISPIDSPTSI_SelectionOffset',
    'SPEI_PROPERTY_NUM_CHANGE', 'SPAUDIOBUFFERINFO',
    'SVSFParseAutodetect', 'SECFIgnoreKanaType',
    'SpeechGrammarRuleStateTransitionType',
    'DISPID_SOTGetDescription', 'DISPID_SABIBufferSize',
    'DISPID_SMSGetData', 'DISPID_SABufferInfo', 'SVPAlert',
    'DISPID_SVEStreamEnd', 'SPINTERFERENCE', 'DISPID_SRCEStartStream',
    'SDKLLocalMachine', 'SPPS_RESERVED2',
    'DISPID_SOTGetStorageFileName', 'ISpeechPhraseAlternates',
    'DISPID_SRGSetTextSelection', 'SAFT48kHz8BitMono',
    'ISpeechRecoResult2', 'DISPID_SPRuleNumberOfElements',
    'SPEI_VOICE_CHANGE', 'SECHighConfidence', 'SPBO_PAUSE',
    'SAFTExtendedAudioFormat', 'DISPID_SRCVoice', 'SVSFParseSsml',
    'DISPID_SRCBookmark', 'IInternetSecurityManager', 'SP_VISEME_8',
    'SpeechGrammarTagDictation', 'ISpRecoResult',
    'DISPID_SRCEEndStream', 'eLEXTYPE_PRIVATE18', 'SPAR_High',
    'SPAS_RUN', 'DISPID_SPRsItem', 'SRERecoOtherContext',
    'SAFTADPCM_44kHzMono', 'DISPID_SGRSTPropertyId', 'SVEPrivate',
    'DISPID_SRCRecognizer', 'DISPID_SPRulesCount',
    'DISPID_SpeechPhraseRules', 'eLEXTYPE_PRIVATE14', 'SPVPRI_ALERT',
    'SDTReplacement', 'STSF_LocalAppData', 'DISPID_SFSOpen',
    'SPPS_RESERVED4', 'DISPID_SpeechPhraseReplacement',
    'SVSFIsFilename', 'STSF_AppData', 'SPCT_SUB_COMMAND',
    'ISpeechGrammarRules', 'SRAONone', 'DISPID_SLGetWords',
    'SAFTADPCM_8kHzMono', 'DISPID_SVSLastStreamNumberQueued',
    'SPPS_Verb', 'DISPID_SRRAudioFormat', 'SPVPRI_OVER',
    'DISPID_SRCEPropertyStringChange', 'SGDisplay', 'DISPID_SAVolume',
    'SVP_1', 'DISPID_SLWsCount', 'ISpeechLexiconPronunciations',
    'SpeechPropertyHighConfidenceThreshold',
    'DISPID_SPIRetainedSizeBytes', 'SPWF_INPUT', 'SAFT8kHz8BitStereo',
    'DISPID_SDKSetBinaryValue', 'SpeechRecoEvents',
    'SDA_One_Trailing_Space', 'SPSNotOverriden',
    'DISPID_SRCEBookmark', 'DISPID_SPIEngineId',
    'DISPID_SRGRecoContext', 'DISPID_SPIAudioSizeTime',
    'SAFTCCITT_ALaw_11kHzMono', 'eLEXTYPE_PRIVATE8',
    'DISPID_SAFSetWaveFormatEx', 'DISPID_SGRSTNextState',
    '_ISpeechVoiceEvents', 'SVP_8', 'SpeechPropertyResponseSpeed',
    'DISPID_SGRInitialState', 'DISPID_SASFreeBufferSpace',
    'SPVPRIORITY', 'DISPID_SPRDisplayAttributes',
    'SpeechPropertyLowConfidenceThreshold',
    'DISPID_SpeechAudioStatus', 'SpeechAllElements',
    'SPWP_UNKNOWN_WORD_UNPRONOUNCEABLE', 'SpMemoryStream',
    'DISPID_SVEEnginePrivate', 'SpeechTokenShellFolder',
    'DISPID_SPELexicalForm', 'DISPID_SpeechPhraseAlternates',
    'SGRSTTRule', 'SPAO_NONE', 'SAFT44kHz8BitMono',
    'DISPID_SGRSTs_NewEnum', 'DISPID_SLGetPronunciations',
    'SpeechCategoryPhoneConverters', 'SpeechAudioFormatGUIDText',
    'DISPID_SAFGuid', 'DISPID_SGRSTPropertyValue', 'SPRULESTATE',
    'SPLEXICONTYPE', 'SRTStandard', 'ISpeechLexiconWords',
    'DISPID_SGRsCommit', 'SVSFUnusedFlags', 'SSTTWildcard',
    'SPXMLRESULTOPTIONS', 'DISPID_SGRs_NewEnum', 'ISpResourceManager',
    'ISpRecoContext', 'SP_VISEME_13', 'SDA_Consume_Leading_Spaces',
    'DISPID_SGRsCount', 'DISPID_SGRSTsCount',
    'SPSMF_SRGS_SEMANTICINTERPRETATION_W3C', 'SPSEMANTICFORMAT',
    'SPAR_Medium', 'SPDKL_DefaultLocation', 'SpeechWordType',
    'ISpeechLexiconWord', 'DISPID_SVSInputWordLength',
    'SPSERIALIZEDRESULT', 'ISpeechAudioBufferInfo', 'ISpRecognizer',
    'DISPID_SVEventInterests', 'SGLexicalNoSpecialChars',
    'SAFTCCITT_uLaw_8kHzMono', 'SPRECOGNIZERSTATUS',
    'DISPID_SRCEFalseRecognition', 'SINone', 'SVP_10',
    'DISPID_SPAsCount', 'DISPID_SBSSeek', 'SpStream',
    'SPPS_Noncontent', 'SpeechStreamFileMode', 'DISPID_SPCLangId',
    'typelib_path', 'DISPID_SLWWord', 'SSFMCreate',
    'SPWT_LEXICAL_NO_SPECIAL_CHARS', 'DISPID_SADefaultFormat',
    'DISPID_SpeechObjectTokens', 'SREBookmark',
    'SAFTGSM610_22kHzMono', 'DISPID_SLRemovePronunciationByPhoneIds',
    'SVF_Stressed', 'SAFTText', 'DISPID_SLAddPronunciation',
    'DISPID_SLPType', 'SPAR_Low', 'SP_VISEME_18',
    'DISPID_SPERetainedSizeBytes', 'SAFTCCITT_ALaw_8kHzStereo',
    'DISPID_SpeechMemoryStream', 'SREPropertyStringChange',
    'SVSFNLPSpeakPunc', 'DISPID_SVEStreamStart',
    'eLEXTYPE_USER_SHORTCUT', 'DISPID_SRProfile',
    'SPRST_ACTIVE_ALWAYS', 'SVP_6', 'SECFNoSpecialChars',
    'SRADynamic', 'ISpPhoneticAlphabetConverter',
    'DISPID_SASCurrentDevicePosition', 'SpeechAudioFormatType',
    'DISPID_SWFEChannels', 'SAFTCCITT_uLaw_44kHzMono',
    'DISPID_SOTsCount', 'DISPID_SPIGetText', 'SVP_20',
    'DISPID_SWFEBlockAlign', 'SVEBookmark', 'SPAS_STOP', 'SRAExport',
    'eLEXTYPE_PRIVATE16', 'DISPID_SPCPhoneToId', 'DISPID_SGRAddState',
    'DISPID_SOTRemove', 'DISPID_SPEDisplayAttributes', 'SRTEmulated',
    'SPRST_NUM_STATES', 'SITooQuiet', 'SPCT_SUB_DICTATION',
    'ISpeechPhraseReplacement', 'DISPID_SPPsItem', 'SREStateChange',
    'DISPID_SOTMatchesAttributes', 'DISPID_SRAudioInput',
    'SpeechRetainedAudioOptions',
    'DISPID_SRCAudioInInterferenceStatus', 'ISpeechMMSysAudio',
    'SPEI_RESERVED3', 'SpeechTokenKeyUI', 'DISPID_SRGCmdSetRuleState',
    'DISPID_SGRClear', 'SAFT24kHz16BitStereo', 'DISPID_SpeechVoice',
    'SPWORD', 'DISPID_SPRuleChildren', 'SAFTNonStandardFormat',
    'SECFIgnoreCase', 'DISPID_SRGCmdLoadFromObject', 'SPEI_RESERVED1',
    'SAFTNoAssignedFormat', 'ISpeechTextSelectionInformation',
    'ISpeechPhraseInfo', 'DISPID_SRRSpeakAudio', 'SAFT11kHz16BitMono',
    'SPGRAMMARWORDTYPE', 'ISpeechRecoGrammar', 'SAFT11kHz16BitStereo',
    '__MIDL___MIDL_itf_sapi_0000_0020_0002', 'DISPID_SPRuleName',
    'DISPID_SRRGetXMLErrorInfo', 'DISPID_SRSetPropertyString',
    'eLEXTYPE_MORPHOLOGY', 'ISpVoice', 'SVP_0', 'SPSInterjection',
    'DISPID_SVIsUISupported', 'DISPID_SPPParent',
    'DISPID_SpeechWaveFormatEx', 'DISPID_SPANumberOfElementsInResult',
    'DISPID_SPRuleParent', 'SPCATEGORYTYPE', 'DISPID_SMSALineId',
    'SRERequestUI', 'SPSLMA', 'SPEI_INTERFERENCE', 'SVP_2',
    'DISPID_SpeechVoiceStatus', 'DISPID_SRRDiscardResultInfo',
    'SVSFNLPMask', 'DISPID_SPPsCount', 'SpInProcRecoContext',
    'DISPID_SpeechRecoResultTimes', 'SP_VISEME_1',
    'eWORDTYPE_DELETED', 'SAFT48kHz8BitStereo', 'SP_VISEME_9',
    'SPSNoun', 'SpeechDictationTopicSpelling', 'SVPNormal',
    'SRESoundStart', 'STCLocalServer', 'SPPS_RESERVED1',
    'DISPID_SpeechRecoContextEvents', 'SpeechVoiceCategoryTTSRate',
    'SREStreamStart', 'SpLexicon', 'SRTAutopause',
    'SAFT44kHz16BitMono', 'DISPID_SRRTimes', 'SECNormalConfidence',
    'SpeechTokenValueCLSID', 'SPWT_LEXICAL', 'SPSModifier',
    'eLEXTYPE_PRIVATE1', 'SPSEMANTICERRORINFO',
    'SAFTCCITT_uLaw_44kHzStereo', 'DISPID_SGRSTPropertyName',
    'ISpeechBaseStream', 'DISPID_SVEWord', 'SPCT_COMMAND',
    'ISpeechVoiceStatus', 'SAFT8kHz16BitStereo',
    'DISPID_SpeechCustomStream', 'SDTAudio',
    'DISPID_SRCEInterference', 'DISPID_SVEPhoneme',
    'SAFTCCITT_ALaw_8kHzMono', 'SPEI_FALSE_RECOGNITION',
    'DISPID_SOTCDefault', 'eLEXTYPE_RESERVED6',
    'ISpeechLexiconPronunciation', 'DISPID_SBSFormat', 'SPSHT_EMAIL',
    'SVP_11', 'SPEI_PHRASE_START',
    'DISPID_SpeechGrammarRuleStateTransitions',
    'SpeechStreamSeekPositionType', 'ISpeechAudioFormat',
    'SAFT44kHz8BitStereo', 'SGLexical', 'ISpPhrase',
    'eLEXTYPE_RESERVED10', 'SpeechPropertyComplexResponseSpeed',
    'SINoise', 'SP_VISEME_11', 'ISpeechPhraseRules',
    'SpNotifyTranslator', 'DISPID_SDKEnumValues',
    'SpeechAudioFormatGUIDWave', 'DISPID_SVEViseme',
    'SpObjectTokenCategory', 'DISPID_SRCERecognition',
    'DISPID_SRCSetAdaptationData', 'ISpAudio',
    'DISPID_SPIReplacements', 'SAFTADPCM_44kHzStereo',
    'DISPID_SRCESoundEnd', 'SGPronounciation', 'SVP_19',
    'ISpeechResourceLoader', 'SDTAlternates',
    'DISPID_SPRuleConfidence', 'tagSPTEXTSELECTIONINFO',
    'SpeechRegistryLocalMachineRoot', 'DISPID_SVGetVoices',
    'eLEXTYPE_PRIVATE9', 'DISPID_SDKDeleteValue',
    'ISpNotifyTranslator', 'Speech_StreamPos_RealTime', 'SPSUnknown',
    'DISPID_SPRText', 'SPEI_PROPERTY_STRING_CHANGE',
    'SPEI_ACTIVE_CATEGORY_CHANGED', 'SASClosed', 'SVEWordBoundary',
    'DISPID_SAFGetWaveFormatEx', 'SAFT32kHz16BitMono',
    'SAFT22kHz16BitMono', 'SPAS_PAUSE', 'SPEI_SR_RETAINEDAUDIO',
    'DISPID_SLGenerationId', 'SpeechUserTraining', 'SRTReSent',
    'DISPID_SpeechGrammarRules', 'DISPID_SPRuleFirstElement',
    'eLEXTYPE_PRIVATE11', 'SPEI_RECO_OTHER_CONTEXT',
    'SPDKL_CurrentUser', 'SPPHRASEPROPERTY',
    'DISPID_SRGCmdLoadFromMemory', 'DISPID_SRRSaveToMemory',
    'ISpProperties', 'SSSPTRelativeToStart',
    'SDA_Two_Trailing_Spaces', 'SVSFDefault', 'SITooLoud',
    'eWORDTYPE_ADDED', 'SAFTCCITT_ALaw_22kHzStereo',
    'SPSERIALIZEDPHRASE', 'SAFT16kHz8BitStereo', 'SPEVENTSOURCEINFO',
    'Speech_Max_Pron_Length', 'DISPID_SGRAddResource',
    'DISPID_SRCCreateGrammar', 'SGRSTTTextBuffer',
    'DISPID_SPIEnginePrivateData', 'SPRST_ACTIVE',
    'SpeechRegistryUserRoot', 'SGSEnabled', 'ISpeechPhraseProperty',
    'SPEI_START_INPUT_STREAM', 'SpVoice', 'SSTTDictation',
    'SpeechEmulationCompareFlags', 'DISPID_SABIEventBias',
    'DISPID_SVSInputSentencePosition', 'SVESentenceBoundary',
    'SAFT48kHz16BitMono', 'DISPID_SPEAudioStreamOffset',
    'DISPID_SPEPronunciation', 'ISpeechAudioStatus',
    'DISPID_SpeechRecoContext', 'SPEI_RECOGNITION', 'SGDSActive',
    'SAFTCCITT_uLaw_22kHzMono', 'DISPID_SPPValue',
    'SAFT32kHz16BitStereo', 'SPPHRASEELEMENT', 'DISPID_SVResume',
    'SFTInput', 'ISpXMLRecoResult', 'DISPID_SPPEngineConfidence',
    'SAFTADPCM_22kHzStereo', 'SPSHT_NotOverriden',
    'DISPID_SOTCreateInstance', 'SVSFIsXML', 'DISPID_SMSAMMHandle',
    'SPFM_CREATE_ALWAYS', 'SPRECORESULTTIMES',
    'DISPID_SDKSetLongValue', 'DISPID_SWFEFormatTag', 'SPPS_Noun',
    'DISPID_SpeechRecoResult2', 'SPCONTEXTSTATE', 'IEnumString',
    'DISPID_SRSCurrentStreamPosition', 'SpeechTokenIdUserLexicon',
    'DISPID_SOTSetId', 'SREPropertyNumChange', 'SECLowConfidence',
    'SPWP_UNKNOWN_WORD_PRONOUNCEABLE', 'SpeechVoiceSpeakFlags',
    'SpShortcut', 'SAFT12kHz16BitMono', 'ISpeechLexicon',
    'SPAUDIOOPTIONS', 'DISPID_SPEs_NewEnum', 'SBOPause',
    'ISpObjectTokenCategory', 'SREInterference', 'SASPause',
    'DISPID_SGRId', 'SVEStartInputStream', 'ISpeechXMLRecoResult',
    'SASRun', '__MIDL___MIDL_itf_sapi_0000_0020_0001', 'SpFileStream',
    'DISPID_SRCCreateResultFromMemory', 'DISPIDSPTSI_ActiveLength',
    'SAFT12kHz16BitStereo', 'DISPID_SpeechPhraseProperty',
    'SpeechVoiceEvents', 'SPEI_RESERVED5', 'DISPID_SAStatus',
    'DISPID_SVAudioOutputStream', 'SPEI_SR_PRIVATE', 'SPEI_MAX_TTS',
    'SPWP_KNOWN_WORD_PRONOUNCEABLE', 'DISPID_SpeechGrammarRuleState',
    'SpMMAudioEnum', 'SpeechVoiceSkipTypeSentence', 'SRCS_Disabled',
    'SRARoot', 'SpeechRuleAttributes', 'DISPID_SPEAudioSizeTime',
    'SPINTERFERENCE_LATENCY_TRUNCATE_BEGIN', 'SPEVENTENUM',
    'DISPID_SGRSAddSpecialTransition', 'DISPID_SRCEPhraseStart',
    'SAFTCCITT_uLaw_11kHzStereo', 'eLEXTYPE_RESERVED8',
    'SPINTERFERENCE_NOSIGNAL', 'DISPID_SRDisplayUI',
    'SpSharedRecoContext', 'ISpeechRecoContext',
    'DISPID_SOTRemoveStorageFileName', 'SAFTGSM610_8kHzMono',
    'DISPID_SLWType', 'SpeechCategoryVoices',
    'ISpeechGrammarRuleStateTransition', 'SPEI_SENTENCE_BOUNDARY',
    'Speech_Default_Weight', 'SAFTCCITT_ALaw_44kHzStereo',
    'DISPID_SPAStartElementInResult', 'eLEXTYPE_PRIVATE3',
    'SPEI_END_INPUT_STREAM', 'SPSMF_SRGS_SEMANTICINTERPRETATION_MS',
    'ISpeechCustomStream', 'DISPID_SLWsItem', 'SpeechBookmarkOptions',
    'DISPID_SPPNumberOfElements', 'SPINTERFERENCE_TOOQUIET',
    'DISPID_SVSLastBookmarkId', 'SpeechCategoryAudioIn',
    'SPPS_RESERVED3', 'SLTApp', 'SPRECOCONTEXTSTATUS',
    'Speech_Max_Word_Length', 'SVP_9', 'SAFT24kHz8BitMono',
    'DISPID_SPAsItem', 'SpPhoneticAlphabetConverter', 'SGRSTTWord',
    'DISPID_SLRemovePronunciation', 'DISPID_SVAlertBoundary',
    'ISpeechPhoneConverter', 'DISPID_SOTsItem', 'SPPROPERTYINFO',
    'ISpeechRecognizer', 'DISPID_SRGState', 'DISPID_SLPsCount',
    'ISpeechObjectToken', 'DISPID_SRGSetWordSequenceData',
    'DISPID_SRCRetainedAudio', 'DISPID_SGRSTWeight',
    'DISPID_SCSBaseStream', 'SP_VISEME_14', 'DISPID_SVVoice',
    'DISPID_SPEAudioTimeOffset', 'eLEXTYPE_RESERVED7',
    'DISPID_SVGetAudioInputs', 'SPSMF_SAPI_PROPERTIES',
    'DISPID_SPISaveToMemory', 'DISPID_SRRRecoContext',
    'ISpeechPhraseAlternate', 'SPAS_CLOSED', 'eLEXTYPE_APP',
    'DISPID_SLPLangId', 'DISPID_SpeechGrammarRule',
    'DISPID_SPIAudioStreamPosition', 'DISPID_SVSpeak',
    'STCInprocServer', 'SAFTCCITT_uLaw_8kHzStereo',
    'DISPID_SRSetPropertyNumber', 'SPEI_SOUND_END', 'SP_VISEME_3',
    'DISPID_SRCRetainedAudioFormat', 'SVEVoiceChange',
    'SAFT48kHz16BitStereo', 'SPEI_MIN_SR', 'DISPID_SLPPartOfSpeech',
    'ISpeechObjectTokens', 'SPEI_RESERVED2', 'SSFMOpenReadWrite',
    'SRSActiveAlways', 'SPFM_CREATE', 'SREPhraseStart',
    'SpTextSelectionInformation', 'SPFM_NUM_MODES',
    'DISPID_SRAudioInputStream', 'SREStreamEnd', 'Library',
    'DISPID_SPPId', 'DISPID_SVVolume', 'DISPID_SWFEBitsPerSample',
    'SREAdaptation', 'DISPID_SWFESamplesPerSec', 'SECFDefault',
    'SPEI_REQUEST_UI', 'DISPID_SpeechFileStream', '_SPAUDIOSTATE',
    'ISpeechDataKey', 'DISPID_SRState',
    'DISPID_SpeechObjectTokenCategory', 'SLODynamic',
    'SPCT_DICTATION', 'SP_VISEME_5', 'DISPID_SpeechAudio',
    'SpeechCategoryAudioOut', 'SPEI_ADAPTATION',
    'SPINTERFERENCE_TOOLOUD', 'SVP_21', 'SRTSMLTimeout',
    'SAFT8kHz16BitMono', 'SPEI_PHONEME',
    'DISPID_SGRSAddRuleTransition', 'SDTPronunciation',
    'DISPID_SVSInputWordPosition', 'SPBO_TIME_UNITS',
    'ISpRecoGrammar', 'DISPID_SVESentenceBoundary', 'ISpLexicon',
    'DISPID_SVEBookmark', 'SLOStatic',
    'ISpeechGrammarRuleStateTransitions', 'SDTDisplayText',
    'DISPID_SPIGetDisplayAttributes', 'STCInprocHandler',
    'SpUnCompressedLexicon', 'SPLO_DYNAMIC', 'eLEXTYPE_PRIVATE13',
    'SPINTERFERENCE_LATENCY_WARNING', 'STSF_FlagCreate',
    'DISPID_SASetState', 'STSF_CommonAppData', 'SP_VISEME_20',
    '_RemotableHandle', 'DISPID_SVWaitUntilDone', 'ISpPhraseAlt',
    'DISPID_SRSClsidEngine', 'SAFT16kHz16BitMono',
    'DISPID_SpeechRecoResult', 'DISPID_SRRecognizer', 'SPWORDTYPE',
    'SVP_7', 'SPSFunction', 'SAFT22kHz8BitMono',
    'DISPID_SPILanguageId', 'SpeechAudioState', 'SPCS_DISABLED',
    'DISPID_SRRAudio', 'SPSHT_Unknown', 'DISPID_SFSClose',
    'ISpObjectWithToken', 'SSTTTextBuffer',
    'DISPID_SRGCmdSetRuleIdState', 'SVSFParseSapi',
    'DISPID_SRGetPropertyString', 'DISPID_SPCIdToPhone', 'tagSTATSTG',
    'DISPID_SRCEAdaptation', 'eLEXTYPE_PRIVATE19', 'SPPS_LMA',
    'DISPID_SpeechBaseStream', 'DISPID_SRCEPropertyNumberChange',
    'SAFT12kHz8BitStereo', 'DISPID_SDKSetStringValue',
    'DISPID_SOTCSetId', 'SpeechCategoryRecoProfiles', 'SPSVerb',
    'SpeechTokenKeyFiles', 'DISPID_SLPSymbolic',
    'DISPID_SVEAudioLevel', 'SpeechRecoContextState',
    'SpeechLexiconType', 'SpeechInterference', 'DISPID_SGRSRule',
    'eLEXTYPE_USER', 'DISPID_SPRuleId', 'SVP_14',
    'DISPID_SVSInputSentenceLength', 'DISPID_SOTId',
    'DISPID_SOTDisplayUI', 'SpInprocRecognizer',
    'DISPID_SpeechVoiceEvent', 'SPPHRASE', 'DISPID_SRGReset',
    'Speech_StreamPos_Asap', 'DISPID_SpeechMMSysAudio',
    'DISPID_SpeechPhraseReplacements', 'SAFT22kHz16BitStereo',
    'DISPID_SpeechLexiconPronunciation', 'SpStreamFormatConverter',
    'DISPID_SVSyncronousSpeakTimeout',
    'DISPID_SRGCmdLoadFromProprietaryGrammar', 'tagSPPROPERTYINFO',
    'ISpeechWaveFormatEx', 'DISPID_SpeechGrammarRuleStateTransition',
    'SP_VISEME_17', 'DISPID_SVPriority', 'SPEI_SR_BOOKMARK',
    'DISPID_SGRsAdd', 'SpeechRecognizerState',
    'DISPID_SRGetPropertyNumber', 'SPEI_TTS_AUDIO_LEVEL',
    'SPWORDLIST', 'ISpeechPhraseRule', 'DISPID_SPEAudioSizeBytes',
    'DISPID_SRRTLength', 'SAFTGSM610_44kHzMono', 'ISpRecoGrammar2',
    'SP_VISEME_7', 'DISPID_SRCResume', 'eLEXTYPE_PRIVATE2',
    'DISPID_SPEsItem', 'DISPIDSPRG', 'DISPID_SDKDeleteKey',
    'DISPID_SpeechPhraseAlternate', 'ISpeechPhraseElements',
    'SSFMOpenForRead', 'SAFT24kHz16BitMono', 'SDTLexicalForm',
    'DISPID_SVSCurrentStreamNumber', 'SPPHRASEREPLACEMENT',
    'DISPIDSPTSI_ActiveOffset', 'SPFM_OPEN_READONLY',
    'SAFT44kHz16BitStereo', 'SASStop', 'DISPID_SOTGetAttribute',
    'SPPARTOFSPEECH', 'DISPID_SpeechPhraseBuilder',
    'DISPID_SRAllowAudioInputFormatChangesOnNextSet',
    'DISPID_SRCESoundStart', 'SpeechFormatType',
    'SGDSActiveWithAutoPause', 'DISPID_SOTCId', 'SpResourceManager',
    'SPGS_ENABLED', 'DISPID_SRRTOffsetFromStart',
    'DISPID_SPEDisplayText', 'SPPS_NotOverriden', 'DISPID_SASState',
    'DISPID_SpeechDataKey', 'DISPID_SPAs_NewEnum',
    'SRADefaultToActive', 'DISPID_SPIAudioSizeBytes',
    'DISPID_SRCEventInterests', 'DISPID_SRStatus',
    'SPINTERFERENCE_TOOFAST', 'DISPID_SOTCGetDataKey',
    'SAFTADPCM_11kHzMono', 'SAFT11kHz8BitStereo',
    'IEnumSpObjectTokens', 'SVSFIsNotXML', 'DISPID_SWFEExtraData',
    'SP_VISEME_6', 'ISpGrammarBuilder', 'SAFT16kHz16BitStereo',
    'DISPID_SpeechPhraseRule', 'SPSHORTCUTTYPE', 'ISpShortcut',
    'SPSHORTCUTPAIR', 'SECFEmulateResult', 'DISPID_SRIsUISupported',
    'SRSInactiveWithPurge', 'SAFTADPCM_11kHzStereo',
    'ISpeechGrammarRule', 'DISPID_SpeechRecognizerStatus',
    'DISPID_SPACommit', 'SpCompressedLexicon', 'SVSFlagsAsync',
    'SGDSInactive', 'DISPID_SGRName', 'SP_VISEME_15',
    'DISPID_SVSpeakCompleteEvent', 'SpeechPropertyResourceUsage',
    'SPAR_Unknown', 'IInternetSecurityMgrSite',
    'DISPID_SpeechAudioFormat', 'DISPID_SBSRead',
    'DISPID_SLPPhoneIds', 'DISPID_SpeechPhraseElement',
    'SAFT22kHz8BitStereo', 'ISpStream', 'DISPID_SVSPhonemeId',
    'DISPID_SVRate', 'eLEXTYPE_PRIVATE10',
    'SAFTTrueSpeech_8kHz1BitMono', 'SRAORetainAudio',
    'SpeechGrammarWordType', 'SPRULE', 'ISpeechFileStream',
    'SPCT_SLEEP', 'DISPID_SVGetAudioOutputs', 'SRSEIsSpeaking',
    'DISPID_SRCVoicePurgeEvent', 'DISPID_SGRsDynamic',
    'DISPID_SPIRule', 'SVP_15', 'SP_VISEME_4',
    'DISPID_SRCreateRecoContext', 'DISPID_SVDisplayUI',
    'DISPID_SASNonBlockingIO', 'DISPID_SRCERequestUI',
    'DISPID_SDKCreateKey', 'DISPID_SRRGetXMLResult', 'SREHypothesis',
    'eLEXTYPE_PRIVATE20', 'SDKLCurrentConfig',
    'ISpeechPhraseProperties', 'DISPID_SBSWrite',
    'DISPID_SRGDictationSetState', 'DISPID_SVEVoiceChange',
    'DISPID_SPRNumberOfElements', 'LONG_PTR', 'SITooSlow',
    'SAFTCCITT_ALaw_11kHzStereo', 'SWPUnknownWordPronounceable',
    'DISPID_SRSNumberOfActiveRules', 'SpeechAddRemoveWord',
    'DISPID_SAFType', 'SPBO_NONE', 'ISpPhoneConverter',
    'SPLOADOPTIONS', 'SAFTDefault', 'ISpeechVoice',
    'SAFT12kHz8BitMono', 'DISPID_SpeechAudioBufferInfo'
]

