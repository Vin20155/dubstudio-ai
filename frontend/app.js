// DubStudio AI - Production AI Video Dubbing Dashboard Logic
// Clean Single Page Application connected to real Backend APIs (Whisper, Gemini, Edge-TTS, FFmpeg)

// Application State (Zero Demo Data - Pure Dynamic State)
const appState = {
  projectName: "My Khmer Dub",
  projectStatus: "Draft", // "Draft" | "Processing" | "Completed"
  duration: 0.0,
  currentTime: 0.0,
  isScrubbing: false,
  isPlaying: false,
  activeAudioTrack: "original", // "original" | "dubbed"
  playbackSpeed: 1.0,
  volume: 1.0,
  isMuted: false,
  subtitlesVisible: true,
  subtitles: [], // Zero demo subtitles
  activeSubtitleId: null,
  searchQuery: "",
  statusFilter: "all",
  currentPage: 1,
  pageSize: 10,
  sessionId: null,
  videoUrl: null,
  dubbedVideoUrl: null,
  dubbedAudioUrl: null,
  bgmAudioUrl: null,
  hasServerApiKey: false,
  previewAudio: new Audio(),
  bgmAudio: new Audio(),
  blurSettings: {
    enabled: false,
    preset: "soft",
    x: 0.10,
    y: 0.72,
    w: 0.80,
    h: 0.22,
    strength: 55,
    aspectRatio: "original",
  },
  blurStudio: {
    enabled: false,
    activeBlurId: "blur_1",
    objects: [
      {
        id: "blur_1",
        name: "Blur #1 - Subtitle Mask",
        enabled: true,
        locked: false,
        blurType: "gaussian",
        shape: "rounded_rect",
        strength: 55,
        feather: 10,
        opacity: 100,
        rotation: 0,
        x: 0.10,
        y: 0.72,
        width: 0.80,
        height: 0.22,
        startTime: 0.0,
        endTime: 999999,
        keyframes: [],
      },
    ],
    history: [],
    redoStack: [],
  },
  activeStudioTab: "voice", // "voice" | "subtitles" | "recap"
  recapStudio: {
    activeStyle: "youtube",
    pacing: "normal",
    includeHook: true,
    includeCta: true,
    hybridDialogue: true,
    tonePreset: "youtube_master",
    modelName: "gemini-3.5-flash",
    voice: "km-KH-PisethNeural",
    speed: 1.15,
    volume: 70,
    pitch: 0,
    bgmTrack: "chill",
    bgmVolume: 35,
    duckedVolume: 12,
    isPlayingBgm: false,
    bgmAudioEl: null,
  },
  subtitleStyle: {
    preset: "classic",
    fontFamily: "Kantumruy Pro",
    fontSize: 28,
    fontWeight: "700",
    italic: false,
    uppercase: false,
    letterSpacing: 0,
    lineHeight: 1.4,
    align: "center",
    textColor: "#ffffff",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 3,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 4,
    shadowOffsetX: 2,
    shadowOffsetY: 2,
    bgStyle: "semi", // "none" | "solid" | "semi" | "rounded"
    bgColor: "#000000",
    bgOpacity: 60,
    bgPadding: 8,
    bgRadius: 8,
    posX: 50, // %
    posY: 85, // %
    positionPreset: "bottom-center",
    safeAreaEnabled: false,
    entranceAnim: "none",
    exitAnim: "none",
    wordAnim: "none", // "none" | "wordByWord" | "highlightCurrent" | "karaoke"
    karaokeColor: "#facc15",
    karaokeSpeed: 1.0,
    langMode: "khmer", // "khmer" | "orig" | "dual"
    rotation: 0,
    widthPct: 75,
  },
  subtitleTracks: [
    { id: "track_khmer", name: "Khmer Translation", tag: "Primary", visible: true, locked: false },
    { id: "track_orig", name: "Original Dialogue", tag: "Secondary", visible: true, locked: false },
  ],
  translationEngine: {
    activeProvider: "gemini",
    activeModel: "gemini-3.5-flash",
    style: "natural",
    useContext: true,
    preserveSpeaker: true,
    optimizeDubbing: true,
    useTM: true,
    useGlossary: true,
    enableFallback: true,
    fallbackProvider: "openai",
    providers: [],
    activeJobId: null,
    isTranslating: false,
    selectedSegmentForRegen: null,
  },
  dubbingMode: "fast", // "fast" | "hq"
  subtitleHistory: [],
  subtitleRedoStack: [],
};


// Cached DOM Elements
const ui = {
  // Header
  inputProjectName: document.getElementById("inputProjectName"),
  projectStatusBadge: document.getElementById("projectStatusBadge"),
  projectStatusText: document.getElementById("projectStatusText"),
  headerDuration: document.getElementById("headerDuration"),
  headerResolution: document.getElementById("headerResolution"),
  btnApiKeyTrigger: document.getElementById("btnApiKeyTrigger"),
  keyIconDot: document.getElementById("keyIconDot"),
  btnSaveProject: document.getElementById("btnSaveProject"),
  btnExportModalTrigger: document.getElementById("btnExportModalTrigger"),

  // Video preview
  videoFilenameDisplay: document.getElementById("videoFilenameDisplay"),
  btnReplaceVideo: document.getElementById("btnReplaceVideo"),
  btnUploadLabel: document.getElementById("btnUploadLabel"),
  hiddenVideoUpload: document.getElementById("hiddenVideoUpload"),
  btnTrackOriginal: document.getElementById("btnTrackOriginal"),
  btnTrackDubbed: document.getElementById("btnTrackDubbed"),
  playerAspectWrapper: document.getElementById("playerAspectWrapper"),
  mainVideoPlayer: document.getElementById("mainVideoPlayer"),
  playerEmptyDropzone: document.getElementById("playerEmptyDropzone"),
  btnBrowseEmpty: document.getElementById("btnBrowseEmpty"),
  btnBigPlay: document.getElementById("btnBigPlay"),
  playerLoadingOverlay: document.getElementById("playerLoadingOverlay"),
  loadingOverlayText: document.getElementById("loadingOverlayText"),
  videoSubtitleOverlay: document.getElementById("videoSubtitleOverlay"),
  videoSubOrig: document.getElementById("videoSubOrig"),
  videoSubKhmer: document.getElementById("videoSubKhmer"),

  // Player controls
  playerProgressContainer: document.getElementById("playerProgressContainer"),
  progressBufferedBar: document.getElementById("progressBufferedBar"),
  progressPlayedBar: document.getElementById("progressPlayedBar"),
  playerPlayheadHandle: document.getElementById("playerPlayheadHandle"),
  btnRestartVideo: document.getElementById("btnRestartVideo"),
  btnSmallPlay: document.getElementById("btnSmallPlay"),
  timeCurrent: document.getElementById("timeCurrent"),
  timeTotal: document.getElementById("timeTotal"),
  btnMuteToggle: document.getElementById("btnMuteToggle"),
  iconVolHigh: document.getElementById("iconVolHigh"),
  iconVolMuted: document.getElementById("iconVolMuted"),
  volumeSlider: document.getElementById("volumeSlider"),
  selectPlaybackSpeed: document.getElementById("selectPlaybackSpeed"),
  btnToggleSubPreview: document.getElementById("btnToggleSubPreview"),
  btnToggleBlurPreview: document.getElementById("btnToggleBlurPreview"),
  btnToolbarBlur: document.getElementById("btnToolbarBlur"),
  btnSideToolbarBlur: document.getElementById("btnSideToolbarBlur"),
  editorToolsSidebar: document.getElementById("editorToolsSidebar"),
  btnFullscreen: document.getElementById("btnFullscreen"),

  // Video Blur Multi Overlay & Controls
  videoBlurMultiOverlay: document.getElementById("videoBlurMultiOverlay") || document.getElementById("videoBlurMaskOverlay"),
  blurBgCanvas: document.getElementById("blurBgCanvas"),
  blurRenderedItemsLayer: document.getElementById("blurRenderedItemsLayer"),
  blurMaskBox: document.getElementById("blurMaskBox"),
  blurMaskGlass: document.getElementById("blurMaskGlass"),
  blurRotateStem: document.getElementById("blurRotateStem"),
  blurRotateHandle: document.getElementById("blurRotateHandle"),
  blurActiveTag: document.getElementById("blurActiveTag"),
  blurActiveName: document.getElementById("blurActiveName"),
  blurMaskCoordsBadge: document.getElementById("blurMaskCoordsBadge"),
  blurHandleTop: document.getElementById("blurHandleTop"),
  blurHandleBottom: document.getElementById("blurHandleBottom"),

  // Dubbing & STT Settings
  selectSourceLang: document.getElementById("selectSourceLang"),
  selectTargetLang: document.getElementById("selectTargetLang"),
  selectSttEngine: document.getElementById("selectSttEngine"),
  selectSttModel: document.getElementById("selectSttModel"),
  selectVoiceModel: document.getElementById("selectVoiceModel"),
  selectVoiceStyle: document.getElementById("selectVoiceStyle"),
  rangeVoiceSpeed: document.getElementById("rangeVoiceSpeed"),
  valVoiceSpeed: document.getElementById("valVoiceSpeed"),
  rangeVoicePitch: document.getElementById("rangeVoicePitch"),
  valVoicePitch: document.getElementById("valVoicePitch"),
  chkAutoTranscribe: document.getElementById("chkAutoTranscribe"),
  chkAutoTranslate: document.getElementById("chkAutoTranslate"),
  chkVoiceSync: document.getElementById("chkVoiceSync"),
  chkNoiseReduction: document.getElementById("chkNoiseReduction"),
  chkKhmerSpell: document.getElementById("chkKhmerSpell"),
  chkPreserveBGM: document.getElementById("chkPreserveBGM"),
  selVocalRemovalMethod: document.getElementById("selVocalRemovalMethod"),

  // Video Canvas & Blur Studio
  selectCanvasAspect: document.getElementById("selectCanvasAspect"),
  chkBlurSubtitles: document.getElementById("chkBlurSubtitles"),
  blurSubpanel: document.getElementById("blurSubpanel"),
  blurPresetChips: document.getElementById("blurPresetChips"),
  blurLayersCount: document.getElementById("blurLayersCount"),
  btnAddBlurObject: document.getElementById("btnAddBlurObject"),
  blurLayersList: document.getElementById("blurLayersList"),
  selectBlurType: document.getElementById("selectBlurType"),
  blurShapeSelector: document.getElementById("blurShapeSelector"),
  rangeBlurStrength: document.getElementById("rangeBlurStrength"),
  valBlurStrength: document.getElementById("valBlurStrength"),
  rangeBlurFeather: document.getElementById("rangeBlurFeather"),
  valBlurFeather: document.getElementById("valBlurFeather"),
  rangeBlurOpacity: document.getElementById("rangeBlurOpacity"),
  valBlurOpacity: document.getElementById("valBlurOpacity"),
  rangeBlurRotation: document.getElementById("rangeBlurRotation"),
  valBlurRotation: document.getElementById("valBlurRotation"),
  rangeBlurXPos: document.getElementById("rangeBlurXPos"),
  valBlurXPos: document.getElementById("valBlurXPos"),
  rangeBlurYPos: document.getElementById("rangeBlurYPos"),
  valBlurYPos: document.getElementById("valBlurYPos"),
  rangeBlurHeight: document.getElementById("rangeBlurHeight"),
  valBlurHeight: document.getElementById("valBlurHeight"),
  rangeBlurWidth: document.getElementById("rangeBlurWidth"),
  valBlurWidth: document.getElementById("valBlurWidth"),
  iconCurrentKeyframe: document.getElementById("iconCurrentKeyframe"),
  blurKeyframeCount: document.getElementById("blurKeyframeCount"),
  fieldSubjectProtection: document.getElementById("fieldSubjectProtection"),
  rangeBlurSubjectProtect: document.getElementById("rangeBlurSubjectProtect"),
  valBlurSubjectProtect: document.getElementById("valBlurSubjectProtect"),
  btnPrevKeyframe: document.getElementById("btnPrevKeyframe"),
  btnToggleKeyframe: document.getElementById("btnToggleKeyframe"),
  labelKeyframeToggle: document.getElementById("labelKeyframeToggle"),
  btnNextKeyframe: document.getElementById("btnNextKeyframe"),
  radioAiFace: document.getElementById("radioAiFace"),
  radioAiObject: document.getElementById("radioAiObject"),
  btnDetectFaces: document.getElementById("btnDetectFaces"),
  labelDetectAction: document.getElementById("labelDetectAction"),
  btnApplyAllFaces: document.getElementById("btnApplyAllFaces"),
  detectedFacesPills: document.getElementById("detectedFacesPills"),
  btnDuplicateBlur: document.getElementById("btnDuplicateBlur"),
  btnResetBlur: document.getElementById("btnResetBlur"),
  btnDeleteBlur: document.getElementById("btnDeleteBlur"),

  // Timeline Blur Track
  timelineBlurTrackRow: document.getElementById("timelineBlurTrackRow"),
  timelineBlurBlocksContainer: document.getElementById("timelineBlurBlocksContainer"),

  btnGenerateDub: document.getElementById("btnGenerateDub"),
  btnModeFastDub: document.getElementById("btnModeFastDub"),
  btnModeHqDub: document.getElementById("btnModeHqDub"),
  btnModeMuteDub: document.getElementById("btnModeMuteDub"),
  chkMuteOriginalAudio: document.getElementById("chkMuteOriginalAudio"),
  badgeDubbingSpeed: document.getElementById("badgeDubbingSpeed"),
  estTimeText: document.getElementById("estTimeText"),
  progressPctText: document.getElementById("progressPctText"),
  pipelineProgressFill: document.getElementById("pipelineProgressFill"),
  pipelineStepCaption: document.getElementById("pipelineStepCaption"),

  // Subtitles Section
  subtitlesSummaryCount: document.getElementById("subtitlesSummaryCount"),
  inputSubtitleSearch: document.getElementById("inputSubtitleSearch"),
  btnClearSubtitleSearch: document.getElementById("btnClearSubtitleSearch"),
  selectSubtitleFilter: document.getElementById("selectSubtitleFilter"),
  btnAddSubtitleTop: document.getElementById("btnAddSubtitleTop"),
  btnImportSrt: document.getElementById("btnImportSrt"),
  hiddenSrtImport: document.getElementById("hiddenSrtImport"),
  btnExportSrt: document.getElementById("btnExportSrt"),
  btnAutoGenerateSub: document.getElementById("btnAutoGenerateSub"),
  btnAutoStoryRecap: document.getElementById("btnAutoStoryRecap"),
  labelAutoStoryRecap: document.getElementById("labelAutoStoryRecap"),

  // Subtitle Toolbar
  tbBtnAdd: document.getElementById("tbBtnAdd"),
  tbBtnStoryRecap: document.getElementById("tbBtnStoryRecap"),
  tbBtnAutoTranslate: document.getElementById("tbBtnAutoTranslate"),
  tbBtnFixKhmer: document.getElementById("tbBtnFixKhmer"),
  tbBtnRegenDub: document.getElementById("tbBtnRegenDub"),
  tbBtnRegenDubLabel: document.getElementById("tbBtnRegenDubLabel"),
  tbBtnMerge: document.getElementById("tbBtnMerge"),
  tbBtnSplit: document.getElementById("tbBtnSplit"),
  tbBtnDelete: document.getElementById("tbBtnDelete"),
  tbBtnSyncTiming: document.getElementById("tbBtnSyncTiming"),
  tbBtnDetectSpeakers: document.getElementById("tbBtnDetectSpeakers"),
  tbBtnDetectEmotions: document.getElementById("tbBtnDetectEmotions"),
  tbBtnFindReplace: document.getElementById("tbBtnFindReplace"),

  // Auto Voice Assignment Preview Modal
  modalAutoVoicePreview: document.getElementById("modalAutoVoicePreview"),
  btnCloseAutoVoiceModal: document.getElementById("btnCloseAutoVoiceModal"),
  btnCancelAutoVoice: document.getElementById("btnCancelAutoVoice"),
  btnConfirmAutoVoice: document.getElementById("btnConfirmAutoVoice"),
  voiceStatMaleCount: document.getElementById("voiceStatMaleCount"),
  voiceStatFemaleCount: document.getElementById("voiceStatFemaleCount"),
  voiceStatBoyCount: document.getElementById("voiceStatBoyCount"),
  voiceStatGirlCount: document.getElementById("voiceStatGirlCount"),
  voiceStatCardBoy: document.getElementById("voiceStatCardBoy"),
  voiceStatCardGirl: document.getElementById("voiceStatCardGirl"),
  voiceStatSepBoy: document.getElementById("voiceStatSepBoy"),
  voiceStatSepGirl: document.getElementById("voiceStatSepGirl"),
  voiceSingleSpeakerNotice: document.getElementById("voiceSingleSpeakerNotice"),
  voiceAssignTableBody: document.getElementById("voiceAssignTableBody"),
  voiceAssignFootnote: document.getElementById("voiceAssignFootnote"),

  // Table & Pagination
  chkSelectAllSubs: document.getElementById("chkSelectAllSubs"),
  subtitlesTable: document.getElementById("subtitlesTable"),
  subtitlesTableBody: document.getElementById("subtitlesTableBody"),
  pagTotalCount: document.getElementById("pagTotalCount"),
  btnPagePrev: document.getElementById("btnPagePrev"),
  btnPageNext: document.getElementById("btnPageNext"),
  pageNumbersList: document.getElementById("pageNumbersList"),

  // Timeline
  timelineTrackCanvas: document.getElementById("timelineTrackCanvas"),
  timelineRuler: document.getElementById("timelineRuler"),
  timelineRangeIndicator: document.getElementById("timelineRangeIndicator"),
  timelinePlayhead: document.getElementById("timelinePlayhead"),
  timelinePlayheadBadge: document.getElementById("timelinePlayheadBadge"),
  timelineBlocksContainer: document.getElementById("timelineBlocksContainer"),

  // Bottom Status Bar
  statTotalSubs: document.getElementById("statTotalSubs"),
  statTranslated: document.getElementById("statTranslated"),
  statNeedsReview: document.getElementById("statNeedsReview"),
  audioSyncBadgeText: document.getElementById("audioSyncBadgeText"),
  btnGenerateFinal: document.getElementById("btnGenerateFinal"),

  // Modals
  modalFindReplace: document.getElementById("modalFindReplace"),
  btnCloseFindReplace: document.getElementById("btnCloseFindReplace"),
  btnCancelFindReplace: document.getElementById("btnCancelFindReplace"),
  btnApplyReplace: document.getElementById("btnApplyReplace"),
  inputFindText: document.getElementById("inputFindText"),
  inputReplaceText: document.getElementById("inputReplaceText"),

  apiKeyModal: document.getElementById("apiKeyModal"),
  btnCloseApiKeyModal: document.getElementById("btnCloseApiKeyModal"),
  btnCancelApiKeyModal: document.getElementById("btnCancelApiKeyModal"),
  btnSaveApiKey: document.getElementById("btnSaveApiKey"),
  inputGeminiKey: document.getElementById("inputGeminiKey"),

  exportModal: document.getElementById("exportModal"),
  btnCloseExportModal: document.getElementById("btnCloseExportModal"),
  btnCancelExportModal: document.getElementById("btnCancelExportModal"),
  downloadVideoBtn: document.getElementById("downloadVideoBtn"),
  downloadAudioBtn: document.getElementById("downloadAudioBtn"),
  downloadKhmerAssBtn: document.getElementById("downloadKhmerAssBtn"),
  downloadKhmerSrtBtn: document.getElementById("downloadKhmerSrtBtn"),
  downloadKhmerVttBtn: document.getElementById("downloadKhmerVttBtn"),
  downloadOrigSrtBtn: document.getElementById("downloadOrigSrtBtn"),

  toastContainer: document.getElementById("toastContainer"),

  // Studio Tab Navigation
  studioTabsNav: document.getElementById("studioTabsNav"),
  tabTriggerVoice: document.getElementById("tabTriggerVoice"),
  tabTriggerSubtitles: document.getElementById("tabTriggerSubtitles"),
  tabTriggerRecap: document.getElementById("tabTriggerRecap"),
  subpanelVoiceSettings: document.getElementById("subpanelVoiceSettings"),
  subpanelSubtitleStudio: document.getElementById("subpanelSubtitleStudio"),
  subpanelRecapStudio: document.getElementById("subpanelRecapStudio"),
  btnSideToolbarSubtitles: document.getElementById("btnSideToolbarSubtitles"),
  btnSideToolbarRecap: document.getElementById("btnSideToolbarRecap"),

  // Recap Studio UI Elements
  recapStyleGrid: document.getElementById("recapStyleGrid"),
  chkRecapHook: document.getElementById("chkRecapHook"),
  chkRecapCta: document.getElementById("chkRecapCta"),
  chkRecapHybrid: document.getElementById("chkRecapHybrid"),
  recapTonePresetsGrid: document.getElementById("recapTonePresetsGrid"),
  selectRecapPacing: document.getElementById("selectRecapPacing"),
  selectRecapModel: document.getElementById("selectRecapModel"),
  btnGenerateRecapScript: document.getElementById("btnGenerateRecapScript"),
  labelGenerateRecapScript: document.getElementById("labelGenerateRecapScript"),
  selectRecapVoice: document.getElementById("selectRecapVoice"),
  rangeRecapSpeed: document.getElementById("rangeRecapSpeed"),
  valRecapSpeed: document.getElementById("valRecapSpeed"),
  rangeRecapVolume: document.getElementById("rangeRecapVolume"),
  valRecapVolume: document.getElementById("valRecapVolume"),
  rangeRecapPitch: document.getElementById("rangeRecapPitch"),
  valRecapPitch: document.getElementById("valRecapPitch"),
  selectRecapBgm: document.getElementById("selectRecapBgm"),
  btnRecapPreviewBgm: document.getElementById("btnRecapPreviewBgm"),
  labelBgmPlay: document.getElementById("labelBgmPlay"),
  iconBgmPlay: document.getElementById("iconBgmPlay"),
  inputCustomBgm: document.getElementById("inputCustomBgm"),
  rangeRecapBgmVol: document.getElementById("rangeRecapBgmVol"),
  valRecapBgmVol: document.getElementById("valRecapBgmVol"),
  rangeRecapDuckedVol: document.getElementById("rangeRecapDuckedVol"),
  valRecapDuckedVol: document.getElementById("valRecapDuckedVol"),
  btnApplyRecap916: document.getElementById("btnApplyRecap916"),
  btnApplyRecapBlurSub: document.getElementById("btnApplyRecapBlurSub"),
  btnApplyRecapKinetic: document.getElementById("btnApplyRecapKinetic"),
  btnSynthesizeRecapAudio: document.getElementById("btnSynthesizeRecapAudio"),
  labelSynthesizeRecap: document.getElementById("labelSynthesizeRecap"),
  btnRenderRecapVideo: document.getElementById("btnRenderRecapVideo"),

  // AI Settings & Translation Engine UI Elements
  btnAiSettingsTrigger: document.getElementById("btnAiSettingsTrigger"),
  modalAiSettings: document.getElementById("modalAiSettings"),
  btnCloseAiSettingsModal: document.getElementById("btnCloseAiSettingsModal"),
  btnCancelAiSettings: document.getElementById("btnCancelAiSettings"),
  btnSaveAiSettings: document.getElementById("btnSaveAiSettings"),
  tabEngineTrigger: document.getElementById("tabEngineTrigger"),
  tabGlossaryTrigger: document.getElementById("tabGlossaryTrigger"),
  tabMemoryTrigger: document.getElementById("tabMemoryTrigger"),
  tabMonitoringTrigger: document.getElementById("tabMonitoringTrigger"),
  tabUpdatesTrigger: document.getElementById("tabUpdatesTrigger"),
  panelTranslationEngine: document.getElementById("panelTranslationEngine"),
  panelGlossary: document.getElementById("panelGlossary"),
  panelMemory: document.getElementById("panelMemory"),
  panelMonitoring: document.getElementById("panelMonitoring"),
  panelUpdates: document.getElementById("panelUpdates"),
  panelGeneral: document.getElementById("panelGeneral"),
  tabGeneralTrigger: document.getElementById("tabGeneralTrigger"),
  selectGeminiEngineModel: document.getElementById("selectGeminiEngineModel"),
  selectCodeCraftEngineModel: document.getElementById("selectCodeCraftEngineModel"),
  selectOpenAIEngineModel: document.getElementById("selectOpenAIEngineModel"),
  selectGoogleEngineModel: document.getElementById("selectGoogleEngineModel"),
  inputLocalEndpoint: document.getElementById("inputLocalEndpoint"),
  inputLocalModelName: document.getElementById("inputLocalModelName"),
  inputGeminiCustomKey: document.getElementById("inputGeminiCustomKey"),
  inputCodeCraftCustomKey: document.getElementById("inputCodeCraftCustomKey"),
  inputCodeCraftBaseUrl: document.getElementById("inputCodeCraftBaseUrl"),
  inputOpenAICustomKey: document.getElementById("inputOpenAICustomKey"),
  inputGoogleCustomKey: document.getElementById("inputGoogleCustomKey"),
  chkGlobalFallbackEnabled: document.getElementById("chkGlobalFallbackEnabled"),
  selectGlobalFallbackProvider: document.getElementById("selectGlobalFallbackProvider"),

  // Project Translation Block
  selectProjectProvider: document.getElementById("selectProjectProvider"),
  selectProjectModel: document.getElementById("selectProjectModel"),
  selectProjectStyle: document.getElementById("selectProjectStyle"),
  chkUseContext: document.getElementById("chkUseContext"),
  chkPreserveSpeaker: document.getElementById("chkPreserveSpeaker"),
  chkOptimizeDubbing: document.getElementById("chkOptimizeDubbing"),
  chkUseTM: document.getElementById("chkUseTM"),
  chkUseGlossary: document.getElementById("chkUseGlossary"),
  chkEnableFallback: document.getElementById("chkEnableFallback"),
  btnTranslateSubtitlesProject: document.getElementById("btnTranslateSubtitlesProject"),
  labelTranslateBtn: document.getElementById("labelTranslateBtn"),
  btnQuickConfigEngine: document.getElementById("btnQuickConfigEngine"),
  translationLiveCard: document.getElementById("translationLiveCard"),
  liveStatusTitle: document.getElementById("liveStatusTitle"),
  liveProgressFill: document.getElementById("liveProgressFill"),
  liveProgressPct: document.getElementById("liveProgressPct"),
  liveProgressCount: document.getElementById("liveProgressCount"),
  liveProviderPill: document.getElementById("liveProviderPill"),
  liveSegmentPreview: document.getElementById("liveSegmentPreview"),
  liveSegmentLabel: document.getElementById("liveSegmentLabel"),
  liveSegmentText: document.getElementById("liveSegmentText"),
  btnCancelTranslation: document.getElementById("btnCancelTranslation"),

  // Glossary & Memory
  inputGlossarySource: document.getElementById("inputGlossarySource"),
  inputGlossaryTarget: document.getElementById("inputGlossaryTarget"),
  inputGlossaryNotes: document.getElementById("inputGlossaryNotes"),
  btnAddGlossaryTerm: document.getElementById("btnAddGlossaryTerm"),
  tbodyGlossary: document.getElementById("tbodyGlossary"),
  btnRefreshTM: document.getElementById("btnRefreshTM"),
  tbodyTM: document.getElementById("tbodyTM"),
  btnRefreshStats: document.getElementById("btnRefreshStats"),
  tbodyProviderStats: document.getElementById("tbodyProviderStats"),
  statTotalJobs: document.getElementById("statTotalJobs"),
  statTotalSegments: document.getElementById("statTotalSegments"),
  statFailedJobs: document.getElementById("statFailedJobs"),
  statAvgLatency: document.getElementById("statAvgLatency"),

  // Single Segment Regenerate Modal
  modalRegenerateSegment: document.getElementById("modalRegenerateSegment"),
  btnCloseRegenerateModal: document.getElementById("btnCloseRegenerateModal"),
  btnCancelRegen: document.getElementById("btnCancelRegen"),
  btnDoRegenerate: document.getElementById("btnDoRegenerate"),
  btnApplyRegen: document.getElementById("btnApplyRegen"),
  regenSourceTextDisplay: document.getElementById("regenSourceTextDisplay"),
  selectRegenProvider: document.getElementById("selectRegenProvider"),
  selectRegenStyle: document.getElementById("selectRegenStyle"),
  selectRegenTone: document.getElementById("selectRegenTone"),
  textRegenResult: document.getElementById("textRegenResult"),


  // Subtitle Overlay Interactive Bounds & Handles
  subtitleBoxBounds: document.getElementById("subtitleBoxBounds"),
  subRotateStem: document.getElementById("subRotateStem"),
  subRotateHandle: document.getElementById("subRotateHandle"),
  subSelectionTag: document.getElementById("subSelectionTag"),
  subSelectionLabel: document.getElementById("subSelectionLabel"),
  subtitleContentWrap: document.getElementById("subtitleContentWrap"),
  inlineSubtitleEditor: document.getElementById("inlineSubtitleEditor"),
  subtitleSafeAreaOverlay: document.getElementById("subtitleSafeAreaOverlay"),

  // Subtitle Quick Editor
  subActiveSegmentBadge: document.getElementById("subActiveSegmentBadge"),
  subActiveCounter: document.getElementById("subActiveCounter"),
  btnSubNavPrev: document.getElementById("btnSubNavPrev"),
  btnSubNavNext: document.getElementById("btnSubNavNext"),
  btnSubAddCurrent: document.getElementById("btnSubAddCurrent"),
  subTextKhmerInput: document.getElementById("subTextKhmerInput"),
  subTextOrigInput: document.getElementById("subTextOrigInput"),
  selectSubSpeaker: document.getElementById("selectSubSpeaker"),
  selectSubLangMode: document.getElementById("selectSubLangMode"),

  // Subtitle Presets
  subPresetChips: document.getElementById("subPresetChips"),

  // Typography Controls
  subFontFamily: document.getElementById("subFontFamily"),
  rangeSubFontSize: document.getElementById("rangeSubFontSize"),
  valSubFontSize: document.getElementById("valSubFontSize"),
  selectSubFontWeight: document.getElementById("selectSubFontWeight"),
  subAlignGroup: document.getElementById("subAlignGroup"),
  btnSubItalic: document.getElementById("btnSubItalic"),
  btnSubUppercase: document.getElementById("btnSubUppercase"),
  rangeSubLetterSpacing: document.getElementById("rangeSubLetterSpacing"),
  valSubLetterSpacing: document.getElementById("valSubLetterSpacing"),
  rangeSubLineHeight: document.getElementById("rangeSubLineHeight"),
  valSubLineHeight: document.getElementById("valSubLineHeight"),

  // Colors, Stroke & Shadow
  inputSubTextColor: document.getElementById("inputSubTextColor"),
  hexSubTextColor: document.getElementById("hexSubTextColor"),
  rangeSubTextOpacity: document.getElementById("rangeSubTextOpacity"),
  valSubTextOpacity: document.getElementById("valSubTextOpacity"),

  chkSubStroke: document.getElementById("chkSubStroke"),
  subStrokeControls: document.getElementById("subStrokeControls"),
  inputSubStrokeColor: document.getElementById("inputSubStrokeColor"),
  hexSubStrokeColor: document.getElementById("hexSubStrokeColor"),
  rangeSubStrokeWidth: document.getElementById("rangeSubStrokeWidth"),
  valSubStrokeWidth: document.getElementById("valSubStrokeWidth"),

  chkSubShadow: document.getElementById("chkSubShadow"),
  subShadowControls: document.getElementById("subShadowControls"),
  inputSubShadowColor: document.getElementById("inputSubShadowColor"),
  hexSubShadowColor: document.getElementById("hexSubShadowColor"),
  rangeSubShadowBlur: document.getElementById("rangeSubShadowBlur"),
  valSubShadowBlur: document.getElementById("valSubShadowBlur"),
  rangeSubShadowOffsetX: document.getElementById("rangeSubShadowOffsetX"),
  valSubShadowOffsetX: document.getElementById("valSubShadowOffsetX"),
  rangeSubShadowOffsetY: document.getElementById("rangeSubShadowOffsetY"),
  valSubShadowOffsetY: document.getElementById("valSubShadowOffsetY"),

  // Background Box
  selectSubBgStyle: document.getElementById("selectSubBgStyle"),
  subBgControlsGroup: document.getElementById("subBgControlsGroup"),
  inputSubBgColor: document.getElementById("inputSubBgColor"),
  hexSubBgColor: document.getElementById("hexSubBgColor"),
  rangeSubBgOpacity: document.getElementById("rangeSubBgOpacity"),
  valSubBgOpacity: document.getElementById("valSubBgOpacity"),
  rangeSubBgPadding: document.getElementById("rangeSubBgPadding"),
  valSubBgPadding: document.getElementById("valSubBgPadding"),
  rangeSubBgRadius: document.getElementById("rangeSubBgRadius"),
  valSubBgRadius: document.getElementById("valSubBgRadius"),
  rangeSubBgBlur: document.getElementById("rangeSubBgBlur"),
  valSubBgBlur: document.getElementById("valSubBgBlur"),

  // Position & Safe Area
  subPositionGrid: document.getElementById("subPositionGrid"),
  rangeSubPosX: document.getElementById("rangeSubPosX"),
  valSubPosX: document.getElementById("valSubPosX"),
  rangeSubPosY: document.getElementById("rangeSubPosY"),
  valSubPosY: document.getElementById("valSubPosY"),
  chkSubSafeArea: document.getElementById("chkSubSafeArea"),

  // Animation & Karaoke
  selectSubEntrance: document.getElementById("selectSubEntrance"),
  selectSubExit: document.getElementById("selectSubExit"),
  selectSubWordAnim: document.getElementById("selectSubWordAnim"),
  subKaraokeControls: document.getElementById("subKaraokeControls"),
  inputKaraokeColor: document.getElementById("inputKaraokeColor"),
  hexKaraokeColor: document.getElementById("hexKaraokeColor"),
  rangeKaraokeSpeed: document.getElementById("rangeKaraokeSpeed"),
  valKaraokeSpeed: document.getElementById("valKaraokeSpeed"),

  // Tracks & Export
  subTracksList: document.getElementById("subTracksList"),
  chkBurnSubtitlesExport: document.getElementById("chkBurnSubtitlesExport"),
  chkExportModalBurnSubs: document.getElementById("chkExportModalBurnSubs"),
  btnQuickExportAss: document.getElementById("btnQuickExportAss"),
  btnQuickExportSrt: document.getElementById("btnQuickExportSrt"),
  btnQuickExportVtt: document.getElementById("btnQuickExportVtt"),
};

// Player Loading Overlay Helpers (Explicit display & class toggles to prevent stuck spinner)
function showPlayerLoading(text) {
  if (ui.playerLoadingOverlay) {
    if (ui.loadingOverlayText && text) ui.loadingOverlayText.textContent = text;
    ui.playerLoadingOverlay.style.display = "flex";
    ui.playerLoadingOverlay.classList.remove("hidden");
  }
}

function hidePlayerLoading() {
  if (ui.playerLoadingOverlay) {
    ui.playerLoadingOverlay.style.display = "none";
    ui.playerLoadingOverlay.classList.add("hidden");
  }
}

// ==========================================================================
// Initialization
// ==========================================================================
async function initDashboard() {
  // Ensure video loading overlay is unconditionally hidden at startup
  hidePlayerLoading();
  if (ui.videoSubtitleOverlay) {
    ui.videoSubtitleOverlay.style.display = "none";
    ui.videoSubtitleOverlay.classList.add("hidden");
  }

  bindEvents();
  loadSavedPreferences();
  loadGeneralSettings();       // restore canvas + AI toggles from localStorage
  bindGeneralSettingsAutoSave(); // auto-save on every toggle change
  await checkServerConfig();

  // Initial Clean UI Render (No Demo Data)
  function purgeAutofilledSearch() {
    if (ui.inputSubtitleSearch && document.activeElement !== ui.inputSubtitleSearch) {
      if (ui.inputSubtitleSearch.value) {
        ui.inputSubtitleSearch.value = "";
        appState.searchQuery = "";
        if (ui.btnClearSubtitleSearch) ui.btnClearSubtitleSearch.classList.add("hidden");
        renderSubtitlesTable();
      }
    }
  }

  if (ui.inputSubtitleSearch) {
    ui.inputSubtitleSearch.value = "";
  }
  if (ui.btnClearSubtitleSearch) {
    ui.btnClearSubtitleSearch.classList.add("hidden");
  }
  appState.searchQuery = "";

  // Guard against asynchronous browser autofill populating after render
  [50, 150, 300, 600, 1200, 2500].forEach((ms) => setTimeout(purgeAutofilledSearch, ms));
  window.addEventListener("pageshow", purgeAutofilledSearch);
  window.addEventListener("load", purgeAutofilledSearch);

  updateProjectStatus("Draft");
  setTimecodeDisplay(0, 0);
  renderSubtitlesTable();
  renderTimelineBlocks();
  updateStatusMetrics();
  initBatchTranslation();
  initProjectsTab();
}

// ==========================================================================
// Event Bindings
// ==========================================================================
function bindEvents() {
  // Project Name
  ui.inputProjectName.addEventListener("change", (e) => {
    appState.projectName = e.target.value.trim() || "Untitled Project";
    showToast(`Project renamed to "${appState.projectName}"`);
  });

  // Save Project
  ui.btnSaveProject.addEventListener("click", saveProjectLocally);

  // Video Upload / Change
  ui.btnReplaceVideo.addEventListener("click", () => ui.hiddenVideoUpload.click());
  if (ui.btnBrowseEmpty) {
    ui.btnBrowseEmpty.addEventListener("click", (e) => {
      e.stopPropagation();
      ui.hiddenVideoUpload.click();
    });
  }
  if (ui.playerEmptyDropzone) {
    ui.playerEmptyDropzone.addEventListener("click", () => ui.hiddenVideoUpload.click());
  }
  ui.hiddenVideoUpload.addEventListener("change", handleVideoFileSelected);

  // Drag & drop directly on empty dropzone
  if (ui.playerEmptyDropzone) {
    ui.playerEmptyDropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      ui.playerEmptyDropzone.classList.add("dragover");
    });
    ui.playerEmptyDropzone.addEventListener("dragleave", () => {
      ui.playerEmptyDropzone.classList.remove("dragover");
    });
    ui.playerEmptyDropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      ui.playerEmptyDropzone.classList.remove("dragover");
      if (e.dataTransfer.files.length > 0) {
        uploadVideoFile(e.dataTransfer.files[0]);
      }
    });
  }

  // Audio Mode Selector (Original | Khmer Dubbed)
  ui.btnTrackOriginal.addEventListener("click", () => switchAudioTrack("original"));
  ui.btnTrackDubbed.addEventListener("click", () => switchAudioTrack("dubbed"));

  // Play / Pause / Restart Buttons
  ui.btnBigPlay.addEventListener("click", togglePlayPause);
  ui.btnSmallPlay.addEventListener("click", togglePlayPause);
  if (ui.btnRestartVideo) {
    ui.btnRestartVideo.addEventListener("click", () => {
      seekToTime(0);
      showToast("Returned to start (00:00)");
    });
  }

  // Video Element Events
  ui.mainVideoPlayer.addEventListener("click", togglePlayPause);
  ui.mainVideoPlayer.addEventListener("timeupdate", onVideoTimeUpdate);
  ui.mainVideoPlayer.addEventListener("play", () => setPlayState(true));
  ui.mainVideoPlayer.addEventListener("pause", () => setPlayState(false));
  ui.mainVideoPlayer.addEventListener("seeked", onVideoSeeked);
  ui.mainVideoPlayer.addEventListener("loadedmetadata", onVideoMetadataLoaded);
  ui.mainVideoPlayer.addEventListener("ended", () => setPlayState(false));

  // Video Scrubber & Playhead Dragging
  bindPlayheadDragging();

  // Volume & Speed
  ui.volumeSlider.addEventListener("input", (e) => setVolume(parseFloat(e.target.value)));
  ui.btnMuteToggle.addEventListener("click", toggleMute);
  ui.selectPlaybackSpeed.addEventListener("change", (e) => {
    appState.playbackSpeed = parseFloat(e.target.value);
    ui.mainVideoPlayer.playbackRate = appState.playbackSpeed;
  });

  // Fullscreen & Subtitle Overlay Toggle
  ui.btnFullscreen.addEventListener("click", toggleFullscreen);
  ui.btnToggleSubPreview.addEventListener("click", toggleSubtitleOverlay);

  // Dubbing Settings Controls
  if (ui.rangeVoiceSpeed) {
    ui.rangeVoiceSpeed.addEventListener("input", (e) => {
      if (ui.valVoiceSpeed) ui.valVoiceSpeed.textContent = `${parseFloat(e.target.value).toFixed(2)}x`;
    });
  }
  if (ui.rangeVoicePitch) {
    ui.rangeVoicePitch.addEventListener("input", (e) => {
      const val = parseInt(e.target.value);
      if (ui.valVoicePitch) ui.valVoicePitch.textContent = val > 0 ? `+${val}` : `${val}`;
    });
  }

  // STT Engine Selector & Model Dynamic Options
  if (ui.selectSttEngine && ui.selectSttModel) {
    ui.selectSttEngine.addEventListener("change", (e) => {
      const eng = e.target.value;
      ui.selectSttModel.innerHTML = "";
      if (eng === "gemini") {
        ui.selectSttModel.innerHTML = `
          <option value="gemini-3-flash">Gemini 3 Flash (AI Multimodal - Next-Gen)</option>
          <option value="gemini-3.5-flash" selected>Gemini 3.5 Flash (AI Multimodal - ឆ្លាតវៃបំផុត)</option>
          <option value="gemini-3.6-flash">Gemini 3.6 Flash</option>
          <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
          <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
          <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
        `;
      } else if (eng === "sensevoice") {
        ui.selectSttModel.innerHTML = `
          <option value="iic/SenseVoiceSmall" selected>SenseVoiceSmall (Ultra-Fast 50x Audio Recognition)</option>
        `;
      } else {
        ui.selectSttModel.innerHTML = `
          <option value="small" selected>Small (Fast & Sharp - លឿនល្មម)</option>
          <option value="medium">Medium (Studio Accurate - ច្បាស់ខ្ពស់)</option>
          <option value="large-v3">Large-v3 (Cinema Precision - ច្បាស់បំផុត)</option>
          <option value="base">Base (Fastest)</option>
        `;
      }
    });
  }

  // Generate Dubbed Video Button
  ui.btnGenerateDub.addEventListener("click", triggerGeneratePipeline);
  ui.btnGenerateFinal.addEventListener("click", () => {
    triggerGeneratePipeline();
  });

  // Subtitle Table Header Controls
  if (ui.inputSubtitleSearch) {
    // Explicitly ensure clean search on init
    ui.inputSubtitleSearch.value = "";
    appState.searchQuery = "";

    // Clear any autofill detection immediately
    ui.inputSubtitleSearch.addEventListener("animationstart", (e) => {
      if (e.animationName === "onAutofillDetect") {
        ui.inputSubtitleSearch.value = "";
        appState.searchQuery = "";
        if (ui.btnClearSubtitleSearch) ui.btnClearSubtitleSearch.classList.add("hidden");
        renderSubtitlesTable();
      }
    });

    // Prevent accidental drag & drop of timestamps or text selections into search
    ui.inputSubtitleSearch.addEventListener("dragover", (e) => {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = "none";
    });
    ui.inputSubtitleSearch.addEventListener("dragenter", (e) => {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = "none";
    });
    ui.inputSubtitleSearch.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
    });

    ui.inputSubtitleSearch.addEventListener("input", (e) => {
      // If user is not focused on the input, this is browser autofill! Clear it!
      if (document.activeElement !== ui.inputSubtitleSearch) {
        ui.inputSubtitleSearch.value = "";
        appState.searchQuery = "";
        if (ui.btnClearSubtitleSearch) ui.btnClearSubtitleSearch.classList.add("hidden");
        renderSubtitlesTable();
        return;
      }
      appState.searchQuery = e.target.value.toLowerCase().trim();
      appState.currentPage = 1;
      if (ui.btnClearSubtitleSearch) {
        ui.btnClearSubtitleSearch.classList.toggle("hidden", !e.target.value);
      }
      renderSubtitlesTable();
    });
  }

  if (ui.btnClearSubtitleSearch) {
    ui.btnClearSubtitleSearch.addEventListener("click", () => {
      if (ui.inputSubtitleSearch) {
        ui.inputSubtitleSearch.value = "";
        ui.inputSubtitleSearch.focus();
      }
      appState.searchQuery = "";
      ui.btnClearSubtitleSearch.classList.add("hidden");
      renderSubtitlesTable();
    });
  }
  ui.selectSubtitleFilter.addEventListener("change", (e) => {
    appState.statusFilter = e.target.value;
    appState.currentPage = 1;
    renderSubtitlesTable();
  });

  ui.btnAddSubtitleTop.addEventListener("click", addNewSubtitleSegment);
  ui.tbBtnAdd.addEventListener("click", addNewSubtitleSegment);

  // Import / Export SRT
  ui.btnImportSrt.addEventListener("click", () => ui.hiddenSrtImport.click());
  ui.hiddenSrtImport.addEventListener("change", handleSrtImport);
  ui.btnExportSrt.addEventListener("click", exportCurrentSubtitlesSrt);

  // Auto Generate STT & AI Story Recap
  ui.btnAutoGenerateSub.addEventListener("click", triggerAutoTranscription);
  if (ui.btnAutoStoryRecap) {
    ui.btnAutoStoryRecap.addEventListener("click", triggerAiStoryRecap);
  }
  if (ui.tbBtnStoryRecap) {
    ui.tbBtnStoryRecap.addEventListener("click", triggerAiStoryRecap);
  }

  // Subtitle Toolbar
  ui.tbBtnAutoTranslate.addEventListener("click", translateAllSubtitles);
  ui.tbBtnFixKhmer.addEventListener("click", fixKhmerGrammar);
  if (ui.tbBtnRegenDub) {
    ui.tbBtnRegenDub.addEventListener("click", regenerateSelectedDub);
  }
  if (ui.chkSelectAllSubs) {
    ui.chkSelectAllSubs.addEventListener("change", (e) => {
      toggleSelectAllSubtitles(e.target.checked);
    });
  }
  ui.tbBtnMerge.addEventListener("click", mergeSelectedSubtitles);
  ui.tbBtnSplit.addEventListener("click", splitSelectedSubtitle);
  ui.tbBtnDelete.addEventListener("click", deleteSelectedSubtitle);
  ui.tbBtnSyncTiming.addEventListener("click", syncSubtitleTiming);
  if (ui.tbBtnDetectSpeakers) {
    ui.tbBtnDetectSpeakers.addEventListener("click", detectAndAssignSpeakers);
  }
  if (ui.tbBtnDetectEmotions) {
    ui.tbBtnDetectEmotions.addEventListener("click", detectDialogueEmotions);
  }

  // Auto Voice Assignment Preview Modal buttons
  if (ui.btnCloseAutoVoiceModal) {
    ui.btnCloseAutoVoiceModal.addEventListener("click", closeAutoVoicePreviewModal);
  }
  if (ui.btnCancelAutoVoice) {
    ui.btnCancelAutoVoice.addEventListener("click", closeAutoVoicePreviewModal);
  }
  if (ui.modalAutoVoicePreview) {
    ui.modalAutoVoicePreview.addEventListener("click", (e) => {
      if (e.target === ui.modalAutoVoicePreview) closeAutoVoicePreviewModal();
    });
  }
  ui.tbBtnFindReplace.addEventListener("click", openFindReplaceModal);

  if (ui.chkAutoTranscribe) {
    ui.chkAutoTranscribe.addEventListener("change", (e) => {
      if (e.target.checked && appState.sessionId && appState.subtitles.length === 0) {
        triggerAutoTranscription();
      }
    });
  }

  // Global Voice Model / Auto Detect Change Listener
  if (ui.selectVoiceModel) {
    ui.selectVoiceModel.addEventListener("change", (e) => {
      const val = e.target.value;
      if (val === "auto") {
        showToast("✨ Voice: Auto Detect Characters (នឹងចាប់តាមតួអង្គ)");
        if (appState.subtitles.length > 0 && appState.sessionId) {
          detectAndAssignSpeakers();
        }
      } else {
        let vName = "Khmer Male 01";
        let sName = "Speaker 1";
        if (val.includes("SreymomNeural-Girl")) {
          vName = "Khmer Girl 01";
          sName = "Speaker 3 (Girl)";
        } else if (val.includes("PisethNeural-Boy")) {
          vName = "Khmer Boy 01";
          sName = "Speaker 3 (Boy)";
        } else if (val.includes("Sreymom")) {
          vName = "Khmer Female 01";
          sName = "Speaker 2";
        } else {
          vName = "Khmer Male 01";
          sName = "Speaker 1";
        }
        if (appState.subtitles.length > 0) {
          appState.subtitles.forEach((s) => {
            s.voice = vName;
            s.speaker = sName;
          });
          renderSubtitlesTable();
          if (typeof renderTimelineBlocks === "function") renderTimelineBlocks();
        }
        showToast(`Voice set to ${vName} for all subtitles`);
      }
    });
  }

  // Pagination
  ui.btnPagePrev.addEventListener("click", () => changePage(-1));
  ui.btnPageNext.addEventListener("click", () => changePage(1));

  // Timeline Click / Scrub
  if (ui.timelineTrackCanvas) ui.timelineTrackCanvas.addEventListener("click", onTimelineTrackClick);

  // Modals
  if (ui.btnExportModalTrigger) ui.btnExportModalTrigger.addEventListener("click", openExportModal);
  if (ui.btnCloseExportModal) ui.btnCloseExportModal.addEventListener("click", closeExportModal);
  if (ui.btnCancelExportModal) ui.btnCancelExportModal.addEventListener("click", closeExportModal);
  if (ui.exportModal) {
    ui.exportModal.addEventListener("click", (e) => {
      if (e.target === ui.exportModal) closeExportModal();
    });
  }

  if (ui.btnApiKeyTrigger) ui.btnApiKeyTrigger.addEventListener("click", openApiKeyModal);
  if (ui.btnCloseApiKeyModal) ui.btnCloseApiKeyModal.addEventListener("click", closeApiKeyModal);
  if (ui.btnCancelApiKeyModal) ui.btnCancelApiKeyModal.addEventListener("click", closeApiKeyModal);
  if (ui.btnSaveApiKey) ui.btnSaveApiKey.addEventListener("click", saveGeminiApiKey);
  if (ui.apiKeyModal) {
    ui.apiKeyModal.addEventListener("click", (e) => {
      if (e.target === ui.apiKeyModal) closeApiKeyModal();
    });
  }

  if (ui.btnCloseFindReplace) ui.btnCloseFindReplace.addEventListener("click", closeFindReplaceModal);
  if (ui.btnCancelFindReplace) ui.btnCancelFindReplace.addEventListener("click", closeFindReplaceModal);
  if (ui.btnApplyReplace) ui.btnApplyReplace.addEventListener("click", applyFindAndReplace);
  if (ui.modalFindReplace) {
    ui.modalFindReplace.addEventListener("click", (e) => {
      if (e.target === ui.modalFindReplace) closeFindReplaceModal();
    });
  }

  // Global Modal Delegator (catches all backdrop clicks and close/cancel button clicks)
  document.addEventListener("click", (e) => {
    if (!e.target) return;
    // Click directly on modal backdrop
    if (e.target.classList && e.target.classList.contains("modal-backdrop")) {
      e.target.classList.add("hidden");
      return;
    }
    // Click on any close/cancel button or element with data-dismiss="modal"
    const closeTrigger = e.target.closest(
      ".modal-close-btn, [data-dismiss='modal'], #btnCancelExportModal, #btnCancelApiKeyModal, #btnCloseExportModal, #btnCloseApiKeyModal, #btnCloseFindReplace, #btnCancelFindReplace, #btnCloseRegenerateModal, #btnCancelRegen, #btnCloseAutoVoiceModal, #btnCancelAutoVoice, #btnCloseAiSettingsModal, #btnCancelAiSettings"
    );
    if (closeTrigger) {
      const parentModal = closeTrigger.closest(".modal-backdrop");
      if (parentModal) {
        parentModal.classList.add("hidden");
      }
    }
  });

  // Video Canvas, Blur Studio, Subtitle Studio & Story Recap Studio Events
  bindBlurStudioEvents();
  bindSubtitleStudioEvents();
  bindRecapStudioEvents();
  bindTranslationEngineEvents();
  bindStudioSplitLayoutEvents();
  bindVoiceSampleEvents();

  // Global Keyboard Shortcuts
  document.addEventListener("keydown", (e) => {
    // Escape key closes any open modal
    if (e.key === "Escape") {
      const openModals = document.querySelectorAll(".modal-backdrop:not(.hidden)");
      if (openModals.length > 0) {
        e.preventDefault();
        openModals.forEach((m) => m.classList.add("hidden"));
        return;
      }
    }

    if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
    if (e.code === "Space") {
      e.preventDefault();
      togglePlayPause();
    } else if (e.code === "ArrowLeft") {
      e.preventDefault();
      seekRelative(-3);
    } else if (e.code === "ArrowRight") {
      e.preventDefault();
      seekRelative(3);
    } else if (e.code === "Home") {
      e.preventDefault();
      seekToTime(0);
      showToast("Returned to start (00:00)");
    }
  });
}

// ==========================================================================
// Media File Uploading & Backend Integration
// ==========================================================================
function handleVideoFileSelected(e) {
  const file = e.target.files[0];
  if (file) {
    uploadVideoFile(file);
  }
}

async function uploadVideoFile(file) {
  ui.videoFilenameDisplay.textContent = file.name;
  ui.btnUploadLabel.textContent = "Change Video";

  // Local object URL for instantaneous preview
  const localUrl = URL.createObjectURL(file);
  ui.mainVideoPlayer.src = localUrl;
  appState.videoUrl = localUrl;

  // Reveal player UI
  if (ui.playerEmptyDropzone) ui.playerEmptyDropzone.classList.add("hidden");
  ui.btnBigPlay.classList.remove("hidden");

  // Reset any previous search query on video change
  if (ui.inputSubtitleSearch) {
    ui.inputSubtitleSearch.value = "";
  }
  if (ui.btnClearSubtitleSearch) {
    ui.btnClearSubtitleSearch.classList.add("hidden");
  }
  appState.searchQuery = "";

  showToast(`Uploading ${file.name}...`);
  updateProjectStatus("Processing");
  showPlayerLoading("Extracting media & audio stream...");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }

    const data = await res.json();
    appState.sessionId = data.session_id;
    appState.duration = data.duration || 0.0;
    appState.videoUrl = data.video_url || localUrl;

    // Update resolution & metadata
    if (data.width && data.height) {
      ui.headerResolution.textContent = `${data.height}p`;
    } else {
      ui.headerResolution.textContent = "1080p";
    }

    setTimecodeDisplay(appState.currentTime || 0, appState.duration);
    updateTimelineRuler(appState.duration);

    // Enable generation controls
    ui.btnGenerateDub.disabled = false;
    ui.btnGenerateFinal.disabled = false;
    ui.pipelineStepCaption.textContent = "Media ready. Click 'Auto Generate' to transcribe.";

    updateProjectStatus("Draft");
    showToast("Media uploaded successfully! Ready for AI transcription.");

    // Auto-transcribe if toggle enabled
    if (ui.chkAutoTranscribe.checked) {
      triggerAutoTranscription();
    }

  } catch (err) {
    console.error("Upload error:", err);
    showToast(`Upload failed: ${err.message}`);
    updateProjectStatus("Draft");
  } finally {
    hidePlayerLoading();
  }
}

// ==========================================================================
// Video Playback & Synchronization
// ==========================================================================
function togglePlayPause(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  if (!ui.mainVideoPlayer.src && !ui.mainVideoPlayer.currentSrc) {
    ui.hiddenVideoUpload.click();
    return;
  }

  if (ui.mainVideoPlayer.paused) {
    // If video reached the end, restart from 0, otherwise keep the seeked time!
    if (ui.mainVideoPlayer.ended || (appState.duration > 0 && Math.abs(appState.currentTime - appState.duration) < 0.1)) {
      ui.mainVideoPlayer.currentTime = 0;
      appState.currentTime = 0;
    } else if (appState.currentTime > 0) {
      try {
        ui.mainVideoPlayer.currentTime = appState.currentTime;
      } catch (_) { }
    }

    ui.mainVideoPlayer.play().then(() => {
      setPlayState(true);
    }).catch((err) => {
      console.warn("Play error:", err);
    });
  } else {
    ui.mainVideoPlayer.pause();
    setPlayState(false);
  }
}

let playbackAnimFrame = null;
function startPlaybackLoop() {
  if (playbackAnimFrame) cancelAnimationFrame(playbackAnimFrame);
  function step() {
    if (ui.mainVideoPlayer && !ui.mainVideoPlayer.paused && !appState.isScrubbing) {
      appState.currentTime = ui.mainVideoPlayer.currentTime;
      appState.duration = (ui.mainVideoPlayer.duration && !isNaN(ui.mainVideoPlayer.duration) && ui.mainVideoPlayer.duration > 0)
        ? ui.mainVideoPlayer.duration
        : (appState.duration || 0.0);
      updatePlaybackUI(appState.currentTime, appState.duration);
      playbackAnimFrame = requestAnimationFrame(step);
    } else {
      playbackAnimFrame = null;
    }
  }
  playbackAnimFrame = requestAnimationFrame(step);
}

function setPlayState(playing) {
  appState.isPlaying = playing;
  if (playing) {
    if (ui.btnBigPlay) {
      ui.btnBigPlay.classList.add("playing");
      const p1 = ui.btnBigPlay.querySelector(".icon-play");
      const p2 = ui.btnBigPlay.querySelector(".icon-pause");
      if (p1) p1.classList.add("hidden");
      if (p2) p2.classList.remove("hidden");
    }
    if (ui.btnSmallPlay) {
      const p1 = ui.btnSmallPlay.querySelector(".icon-ctrl-play");
      const p2 = ui.btnSmallPlay.querySelector(".icon-ctrl-pause");
      if (p1) p1.classList.add("hidden");
      if (p2) p2.classList.remove("hidden");
    }
    document.body.classList.add("video-playing");
    startPlaybackLoop();
  } else {
    if (ui.btnBigPlay) {
      ui.btnBigPlay.classList.remove("playing");
      const p1 = ui.btnBigPlay.querySelector(".icon-play");
      const p2 = ui.btnBigPlay.querySelector(".icon-pause");
      if (p1) p1.classList.remove("hidden");
      if (p2) p2.classList.add("hidden");
    }
    if (ui.btnSmallPlay) {
      const p1 = ui.btnSmallPlay.querySelector(".icon-ctrl-play");
      const p2 = ui.btnSmallPlay.querySelector(".icon-ctrl-pause");
      if (p1) p1.classList.remove("hidden");
      if (p2) p2.classList.add("hidden");
    }
    document.body.classList.remove("video-playing");
    if (playbackAnimFrame) {
      cancelAnimationFrame(playbackAnimFrame);
      playbackAnimFrame = null;
    }
  }
  updateBlurPreview(appState.currentTime);
}

function onVideoMetadataLoaded() {
  if (ui.mainVideoPlayer.duration && !isNaN(ui.mainVideoPlayer.duration)) {
    appState.duration = ui.mainVideoPlayer.duration;
    if (appState.subtitles && appState.subtitles.length > 0) {
      appState.subtitles = sanitizeSubtitleTimelines(appState.subtitles, 0.05, appState.duration);
      renderSubtitlesTable();
      renderTimelineBlocks();
    }
    if (appState.blurStudio && appState.blurStudio.objects.length > 0) {
      appState.blurStudio.objects.forEach((obj) => {
        if (!obj.endTime || obj.endTime < 90000) {
          obj.endTime = 999999;
        }
      });
      renderTimelineBlurBlocks();
    }
  }
  setTimecodeDisplay(appState.currentTime, appState.duration);
  updateTimelineRuler(appState.duration);
  if (ui.mainVideoPlayer.videoWidth && ui.mainVideoPlayer.videoHeight) {
    const vh = ui.mainVideoPlayer.videoHeight;
    ui.headerResolution.textContent = `${vh}p`;
    if (!appState.blurSettings || !appState.blurSettings.aspectRatio || appState.blurSettings.aspectRatio === "original") {
      setCanvasAspectRatio("original");
    }
  }
  syncOverlayToVideo();
  updateBlurPreview(appState.currentTime);
}

function onVideoTimeUpdate() {
  if (appState.isScrubbing) return;
  appState.currentTime = ui.mainVideoPlayer.currentTime;
  appState.duration = ui.mainVideoPlayer.duration || appState.duration || 0.0;
  updatePlaybackUI(appState.currentTime, appState.duration);
}

function updatePlaybackUI(time, duration) {
  setTimecodeDisplay(time, duration);

  const pct = duration > 0 ? Math.min(100, Math.max(0, (time / duration) * 100)) : 0;
  ui.progressPlayedBar.style.width = `${pct}%`;
  ui.playerPlayheadHandle.style.left = `${pct}%`;
  ui.timelinePlayhead.style.left = `${pct}%`;
  ui.timelinePlayheadBadge.textContent = formatTimecodePrecise(time);

  updateVideoSubtitleOverlay(time);
  highlightActiveTableRowAndTimeline(time);
  updateBlurPreview(time);
}

function setTimecodeDisplay(curr, total) {
  ui.timeCurrent.textContent = formatTimecodePrecise(curr);
  ui.timeTotal.textContent = formatTimecodePrecise(total);
  ui.headerDuration.textContent = formatTimecodePrecise(total);
}

function updateTimelineRuler(total) {
  if (total <= 0) {
    ui.timelineRangeIndicator.textContent = "00:00.00 ───────────────────────────────────── 00:00.00";
    return;
  }
  const tStr = formatTimecodePrecise(total);
  ui.timelineRangeIndicator.textContent = `00:00.00 ───────────────────────────────────── ${tStr}`;

  if (ui.timelineRuler) {
    ui.timelineRuler.innerHTML = `
      <span class="ruler-mark" style="left: 0%;">00:00.00</span>
      <span class="ruler-mark" style="left: 25%;">${formatTimecodePrecise(total * 0.25)}</span>
      <span class="ruler-mark" style="left: 50%;">${formatTimecodePrecise(total * 0.5)}</span>
      <span class="ruler-mark" style="left: 75%;">${formatTimecodePrecise(total * 0.75)}</span>
      <span class="ruler-mark" style="left: 100%;">${tStr}</span>
    `;
  }
}

function getClientXFromEvent(e) {
  if (e.touches && e.touches.length > 0) return e.touches[0].clientX;
  if (e.changedTouches && e.changedTouches.length > 0) return e.changedTouches[0].clientX;
  return e.clientX;
}

// Handles click on the bottom timeline track canvas to seek video
function onTimelineTrackClick(e) {
  const canvas = ui.timelineTrackCanvas;
  if (!canvas || !appState.duration) return;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width) return;
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  seekToTime(ratio * appState.duration);
}

function seekToTime(seconds) {
  if (isNaN(seconds) || seconds < 0) seconds = 0;
  const maxDur = appState.duration > 0 ? appState.duration : (ui.mainVideoPlayer.duration || 0);
  appState.currentTime = maxDur > 0 ? Math.max(0, Math.min(seconds, maxDur)) : Math.max(0, seconds);

  if (ui.mainVideoPlayer) {
    try {
      ui.mainVideoPlayer.currentTime = appState.currentTime;
    } catch (_) { }
  }
  updatePlaybackUI(appState.currentTime, appState.duration);
}

function seekRelative(offsetSec) {
  seekToTime(appState.currentTime + offsetSec);
}

let queuedScrubTime = null;
function onVideoSeeked() {
  if (queuedScrubTime !== null && ui.mainVideoPlayer) {
    const next = queuedScrubTime;
    queuedScrubTime = null;
    if (Math.abs(ui.mainVideoPlayer.currentTime - next) > 0.02) {
      try {
        ui.mainVideoPlayer.currentTime = next;
      } catch (_) { }
    }
  }
}

function performVideoFrameScrub(targetTime) {
  queuedScrubTime = targetTime;
  if (!ui.mainVideoPlayer) return;
  if (!ui.mainVideoPlayer.seeking) {
    try {
      ui.mainVideoPlayer.currentTime = targetTime;
    } catch (_) { }
  }
}

function bindPlayheadDragging() {
  let isDraggingPlayer = false;
  let wasPlayingPlayer = false;
  let isDraggingTimeline = false;
  let wasPlayingTimeline = false;

  const getScrubRatio = (clientX, element) => {
    if (!element) return 0;
    const rect = element.getBoundingClientRect();
    if (rect.width <= 0) return 0;
    return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  };

  const applyScrubTime = (targetTime, isFinal = false) => {
    const dur = (ui.mainVideoPlayer.duration && !isNaN(ui.mainVideoPlayer.duration) && ui.mainVideoPlayer.duration > 0)
      ? ui.mainVideoPlayer.duration
      : (appState.duration > 0 ? appState.duration : 0);
    const clampedTime = dur > 0 ? Math.max(0, Math.min(targetTime, dur)) : Math.max(0, targetTime);
    appState.currentTime = clampedTime;

    // Direct, fast UI updating
    const pct = dur > 0 ? (clampedTime / dur) * 100 : 0;
    if (ui.progressPlayedBar) ui.progressPlayedBar.style.width = `${pct}%`;
    if (ui.playerPlayheadHandle) ui.playerPlayheadHandle.style.left = `${pct}%`;
    if (ui.timelinePlayhead) ui.timelinePlayhead.style.left = `${pct}%`;
    if (ui.timelinePlayheadBadge) ui.timelinePlayheadBadge.textContent = formatTimecodePrecise(clampedTime);

    setTimecodeDisplay(clampedTime, dur);
    updateVideoSubtitleOverlay(clampedTime);
    highlightActiveTableRowAndTimeline(clampedTime);
    updateBlurPreview(clampedTime);

    if (isFinal) {
      queuedScrubTime = null;
      if (ui.mainVideoPlayer) {
        try {
          ui.mainVideoPlayer.currentTime = clampedTime;
        } catch (_) { }
      }
    } else {
      performVideoFrameScrub(clampedTime);
    }
  };

  // --- 1. Video Player Progress Bar Dragging (Smooth Pointer Capture) ---
  if (ui.playerProgressContainer) {
    const onPlayerPointerDown = (e) => {
      const dur = (ui.mainVideoPlayer.duration && !isNaN(ui.mainVideoPlayer.duration) && ui.mainVideoPlayer.duration > 0)
        ? ui.mainVideoPlayer.duration
        : (appState.duration > 0 ? appState.duration : 0);
      if (dur <= 0) return;
      if (e.button !== undefined && e.button !== 0 && e.pointerType === 'mouse') return;

      e.preventDefault();
      isDraggingPlayer = true;
      appState.isScrubbing = true;
      wasPlayingPlayer = !ui.mainVideoPlayer.paused;
      if (wasPlayingPlayer) {
        try { ui.mainVideoPlayer.pause(); } catch (_) { }
      }

      ui.playerProgressContainer.classList.add("dragging");
      try {
        ui.playerProgressContainer.setPointerCapture(e.pointerId);
      } catch (_) { }

      const ratio = getScrubRatio(e.clientX, ui.playerProgressContainer);
      applyScrubTime(ratio * dur, false);
    };

    const onPlayerPointerMove = (e) => {
      if (!isDraggingPlayer) return;
      e.preventDefault();
      const dur = (ui.mainVideoPlayer.duration && !isNaN(ui.mainVideoPlayer.duration) && ui.mainVideoPlayer.duration > 0)
        ? ui.mainVideoPlayer.duration
        : (appState.duration > 0 ? appState.duration : 0);
      if (dur <= 0) return;
      const ratio = getScrubRatio(e.clientX, ui.playerProgressContainer);
      applyScrubTime(ratio * dur, false);
    };

    const onPlayerPointerUp = (e) => {
      if (!isDraggingPlayer) return;
      isDraggingPlayer = false;
      appState.isScrubbing = false;
      ui.playerProgressContainer.classList.remove("dragging");

      try {
        if (ui.playerProgressContainer.hasPointerCapture && ui.playerProgressContainer.hasPointerCapture(e.pointerId)) {
          ui.playerProgressContainer.releasePointerCapture(e.pointerId);
        }
      } catch (_) { }

      const dur = (ui.mainVideoPlayer.duration && !isNaN(ui.mainVideoPlayer.duration) && ui.mainVideoPlayer.duration > 0)
        ? ui.mainVideoPlayer.duration
        : (appState.duration > 0 ? appState.duration : 0);
      const ratio = getScrubRatio(e.clientX, ui.playerProgressContainer);
      applyScrubTime(ratio * dur, true);

      // Auto-play immediately from this scrubbed point
      try {
        const playPromise = ui.mainVideoPlayer.play();
        if (playPromise !== undefined) {
          playPromise.then(() => {
            setPlayState(true);
          }).catch((err) => {
            console.warn("Auto-play error:", err);
          });
        }
      } catch (_) { }
    };

    ui.playerProgressContainer.addEventListener("pointerdown", onPlayerPointerDown);
    ui.playerProgressContainer.addEventListener("pointermove", onPlayerPointerMove);
    ui.playerProgressContainer.addEventListener("pointerup", onPlayerPointerUp);
    ui.playerProgressContainer.addEventListener("pointercancel", onPlayerPointerUp);
  }

  // --- 2. Bottom Timeline Track Scrubber Dragging ---
  if (ui.timelineTrackCanvas) {
    const onTimelinePointerDown = (e) => {
      const dur = (ui.mainVideoPlayer.duration && !isNaN(ui.mainVideoPlayer.duration) && ui.mainVideoPlayer.duration > 0)
        ? ui.mainVideoPlayer.duration
        : (appState.duration > 0 ? appState.duration : 0);
      if (dur <= 0) return;
      if (e.button !== undefined && e.button !== 0 && e.pointerType === 'mouse') return;
      if (e.target && (e.target.closest(".timeline-block") || e.target.closest(".timeline-blur-block") || e.target.closest(".btn-blur-track-action"))) {
        return;
      }

      e.preventDefault();
      isDraggingTimeline = true;
      appState.isScrubbing = true;
      wasPlayingTimeline = !ui.mainVideoPlayer.paused;
      if (wasPlayingTimeline) {
        try { ui.mainVideoPlayer.pause(); } catch (_) { }
      }

      try {
        ui.timelineTrackCanvas.setPointerCapture(e.pointerId);
      } catch (_) { }

      const ratio = getScrubRatio(e.clientX, ui.timelineTrackCanvas);
      applyScrubTime(ratio * dur, false);
    };

    const onTimelinePointerMove = (e) => {
      if (!isDraggingTimeline) return;
      e.preventDefault();
      const dur = (ui.mainVideoPlayer.duration && !isNaN(ui.mainVideoPlayer.duration) && ui.mainVideoPlayer.duration > 0)
        ? ui.mainVideoPlayer.duration
        : (appState.duration > 0 ? appState.duration : 0);
      if (dur <= 0) return;
      const ratio = getScrubRatio(e.clientX, ui.timelineTrackCanvas);
      applyScrubTime(ratio * dur, false);
    };

    const onTimelinePointerUp = (e) => {
      if (!isDraggingTimeline) return;
      isDraggingTimeline = false;
      appState.isScrubbing = false;

      try {
        if (ui.timelineTrackCanvas.hasPointerCapture && ui.timelineTrackCanvas.hasPointerCapture(e.pointerId)) {
          ui.timelineTrackCanvas.releasePointerCapture(e.pointerId);
        }
      } catch (_) { }

      const dur = (ui.mainVideoPlayer.duration && !isNaN(ui.mainVideoPlayer.duration) && ui.mainVideoPlayer.duration > 0)
        ? ui.mainVideoPlayer.duration
        : (appState.duration > 0 ? appState.duration : 0);
      const ratio = getScrubRatio(e.clientX, ui.timelineTrackCanvas);
      applyScrubTime(ratio * dur, true);

      // Auto-play immediately from this scrubbed point
      try {
        const playPromise = ui.mainVideoPlayer.play();
        if (playPromise !== undefined) {
          playPromise.then(() => {
            setPlayState(true);
          }).catch((err) => {
            console.warn("Auto-play error:", err);
          });
        }
      } catch (_) { }
    };

    ui.timelineTrackCanvas.addEventListener("pointerdown", onTimelinePointerDown);
    ui.timelineTrackCanvas.addEventListener("pointermove", onTimelinePointerMove);
    ui.timelineTrackCanvas.addEventListener("pointerup", onTimelinePointerUp);
    ui.timelineTrackCanvas.addEventListener("pointercancel", onTimelinePointerUp);
  }

  // Global safety release
  window.addEventListener("pointerup", () => {
    if (isDraggingPlayer || isDraggingTimeline) {
      isDraggingPlayer = false;
      isDraggingTimeline = false;
      appState.isScrubbing = false;
      if (ui.playerProgressContainer) ui.playerProgressContainer.classList.remove("dragging");
    }
  });
  window.addEventListener("pointercancel", () => {
    if (isDraggingPlayer || isDraggingTimeline) {
      isDraggingPlayer = false;
      isDraggingTimeline = false;
      appState.isScrubbing = false;
      if (ui.playerProgressContainer) ui.playerProgressContainer.classList.remove("dragging");
    }
  });
}

function setVolume(val) {
  appState.volume = val;
  ui.mainVideoPlayer.volume = val;
  if (val === 0) {
    ui.iconVolHigh.classList.add("hidden");
    ui.iconVolMuted.classList.remove("hidden");
  } else {
    ui.iconVolHigh.classList.remove("hidden");
    ui.iconVolMuted.classList.add("hidden");
  }
}

function toggleMute() {
  if (ui.mainVideoPlayer.muted || appState.isMuted) {
    ui.mainVideoPlayer.muted = false;
    appState.isMuted = false;
    setVolume(appState.volume || 1);
  } else {
    ui.mainVideoPlayer.muted = true;
    appState.isMuted = true;
    ui.iconVolHigh.classList.add("hidden");
    ui.iconVolMuted.classList.remove("hidden");
  }
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    ui.playerAspectWrapper.requestFullscreen().catch(() => { });
  } else {
    document.exitFullscreen().catch(() => { });
  }
}

function toggleSubtitleOverlay() {
  appState.subtitlesVisible = !appState.subtitlesVisible;
  ui.btnToggleSubPreview.classList.toggle("active-toggle", appState.subtitlesVisible);
  if (!appState.subtitlesVisible) {
    ui.videoSubtitleOverlay.style.display = "none";
    ui.videoSubtitleOverlay.classList.add("hidden");
  } else {
    updateVideoSubtitleOverlay(appState.currentTime);
  }
}

// ==========================================================================
// Video Canvas & Blur Studio Handlers
// ==========================================================================
// ==========================================================================
// Video Canvas & Professional Blur Studio Handlers
// ==========================================================================

function getActiveBlurObject() {
  if (!appState.blurStudio.objects || appState.blurStudio.objects.length === 0) return null;
  if (!appState.blurStudio.activeBlurId) return null;
  const found = appState.blurStudio.objects.find((o) => o.id === appState.blurStudio.activeBlurId);
  return found || null;
}

function ensureActiveBlurObject() {
  let active = getActiveBlurObject();
  if (!active && appState.blurStudio.objects && appState.blurStudio.objects.length > 0) {
    selectBlurObject(appState.blurStudio.objects[0].id);
    active = getActiveBlurObject();
  }
  return active;
}

function deselectBlurObject(commit = true) {
  if (!appState.blurStudio || !appState.blurStudio.activeBlurId) return;
  if (commit) {
    pushBlurHistory();
  }
  appState.blurStudio.activeBlurId = null;
  renderBlurLayersList();
  renderTimelineBlurBlocks();
  updateBlurPreview(appState.currentTime);
}

function pushBlurHistory() {
  const snapshot = JSON.stringify(appState.blurStudio.objects);
  appState.blurStudio.history.push(snapshot);
  if (appState.blurStudio.history.length > 40) {
    appState.blurStudio.history.shift();
  }
  appState.blurStudio.redoStack = [];
}

function undoBlur() {
  if (appState.blurStudio.history.length === 0) return;
  const currentSnap = JSON.stringify(appState.blurStudio.objects);
  appState.blurStudio.redoStack.push(currentSnap);
  const prevSnap = appState.blurStudio.history.pop();
  try {
    appState.blurStudio.objects = JSON.parse(prevSnap);
    const active = getActiveBlurObject();
    if (active) syncBlurControlsFromObject(active);
    renderBlurLayersList();
    renderTimelineBlurBlocks();
    updateBlurPreview(appState.currentTime);
    showToast("Undo blur change");
  } catch (e) {
    console.error("Undo error:", e);
  }
}

function redoBlur() {
  if (appState.blurStudio.redoStack.length === 0) return;
  const currentSnap = JSON.stringify(appState.blurStudio.objects);
  appState.blurStudio.history.push(currentSnap);
  const nextSnap = appState.blurStudio.redoStack.pop();
  try {
    appState.blurStudio.objects = JSON.parse(nextSnap);
    const active = getActiveBlurObject();
    if (active) syncBlurControlsFromObject(active);
    renderBlurLayersList();
    renderTimelineBlurBlocks();
    updateBlurPreview(appState.currentTime);
    showToast("Redo blur change");
  } catch (e) {
    console.error("Redo error:", e);
  }
}

function interpolateBlurAtTime(blurObj, time) {
  const fallback = {
    x: blurObj.x ?? 0.10,
    y: blurObj.y ?? 0.72,
    width: blurObj.width ?? 0.80,
    height: blurObj.height ?? 0.22,
    rotation: blurObj.rotation ?? 0,
    strength: blurObj.strength ?? 55,
    opacity: blurObj.opacity ?? 100,
  };

  if (!blurObj.keyframes || blurObj.keyframes.length === 0) {
    return fallback;
  }

  const kfs = [...blurObj.keyframes].sort((a, b) => a.time - b.time);
  if (time <= kfs[0].time) {
    return { ...fallback, ...kfs[0] };
  }
  if (time >= kfs[kfs.length - 1].time) {
    return { ...fallback, ...kfs[kfs.length - 1] };
  }

  // Find surrounding keyframes
  for (let i = 0; i < kfs.length - 1; i++) {
    const k1 = kfs[i];
    const k2 = kfs[i + 1];
    if (time >= k1.time && time <= k2.time) {
      const span = k2.time - k1.time;
      const t = span > 0 ? (time - k1.time) / span : 0;
      const lerp = (a, b) => a + (b - a) * t;

      return {
        x: lerp(k1.x ?? fallback.x, k2.x ?? fallback.x),
        y: lerp(k1.y ?? fallback.y, k2.y ?? fallback.y),
        width: lerp(k1.width ?? fallback.width, k2.width ?? fallback.width),
        height: lerp(k1.height ?? fallback.height, k2.height ?? fallback.height),
        rotation: lerp(k1.rotation ?? fallback.rotation, k2.rotation ?? fallback.rotation),
        strength: Math.round(lerp(k1.strength ?? fallback.strength, k2.strength ?? fallback.strength)),
        opacity: Math.round(lerp(k1.opacity ?? fallback.opacity, k2.opacity ?? fallback.opacity)),
      };
    }
  }

  return fallback;
}

// Compute the exact rendered sub-rectangle of the video inside playerAspectWrapper
function getVideoRenderedRect() {
  const video = ui.mainVideoPlayer;
  const wrapper = ui.playerAspectWrapper;
  if (!video || !wrapper) return null;

  const wrapperRect = wrapper.getBoundingClientRect();
  const vw = video.videoWidth;
  const vh = video.videoHeight;

  if (!vw || !vh || !wrapperRect.width || !wrapperRect.height) {
    return {
      left: 0,
      top: 0,
      width: wrapperRect.width || 640,
      height: wrapperRect.height || 360,
    };
  }

  const containerRatio = wrapperRect.width / wrapperRect.height;
  const videoRatio = vw / vh;

  let renderedWidth, renderedHeight, offsetX, offsetY;

  if (videoRatio > containerRatio) {
    // Letterbox (black bars top & bottom)
    renderedWidth = wrapperRect.width;
    renderedHeight = wrapperRect.width / videoRatio;
    offsetX = 0;
    offsetY = (wrapperRect.height - renderedHeight) / 2;
  } else {
    // Pillarbox (black bars left & right)
    renderedHeight = wrapperRect.height;
    renderedWidth = wrapperRect.height * videoRatio;
    offsetX = (wrapperRect.width - renderedWidth) / 2;
    offsetY = 0;
  }

  return {
    left: Math.max(0, offsetX),
    top: Math.max(0, offsetY),
    width: Math.min(wrapperRect.width, renderedWidth),
    height: Math.min(wrapperRect.height, renderedHeight),
  };
}

// Synchronize blur and safe area overlays to match the exact visible video bounds
function syncOverlayToVideo() {
  const rect = getVideoRenderedRect();
  if (!rect) return;

  if (ui.videoBlurMultiOverlay) {
    ui.videoBlurMultiOverlay.style.left = `${rect.left}px`;
    ui.videoBlurMultiOverlay.style.top = `${rect.top}px`;
    ui.videoBlurMultiOverlay.style.width = `${rect.width}px`;
    ui.videoBlurMultiOverlay.style.height = `${rect.height}px`;
    ui.videoBlurMultiOverlay.style.right = "auto";
    ui.videoBlurMultiOverlay.style.bottom = "auto";
  }

  if (ui.subtitleSafeAreaOverlay) {
    ui.subtitleSafeAreaOverlay.style.left = `${rect.left}px`;
    ui.subtitleSafeAreaOverlay.style.top = `${rect.top}px`;
    ui.subtitleSafeAreaOverlay.style.width = `${rect.width}px`;
    ui.subtitleSafeAreaOverlay.style.height = `${rect.height}px`;
    ui.subtitleSafeAreaOverlay.style.right = "auto";
    ui.subtitleSafeAreaOverlay.style.bottom = "auto";
  }
}

function updateBlurPreview(time) {
  if (!ui.videoBlurMultiOverlay) return;

  syncOverlayToVideo();

  const isEnabled = appState.blurStudio.enabled;
  if (!isEnabled) {
    ui.videoBlurMultiOverlay.classList.add("hidden");
    ui.videoBlurMultiOverlay.style.display = "none";
    if (ui.blurMaskBox) ui.blurMaskBox.style.display = "none";
    if (ui.blurBgCanvas) {
      ui.blurBgCanvas.classList.add("hidden");
      ui.blurBgCanvas.style.display = "none";
    }
    return;
  }

  ui.videoBlurMultiOverlay.classList.remove("hidden");
  ui.videoBlurMultiOverlay.style.display = "block";

  const activeObj = getActiveBlurObject();

  // Render inactive / other blur regions into blurRenderedItemsLayer
  if (ui.blurRenderedItemsLayer) {
    ui.blurRenderedItemsLayer.innerHTML = "";
    appState.blurStudio.objects.forEach((obj) => {
      // Active object is only handled separately via blurMaskBox when paused
      if (obj.id === appState.blurStudio.activeBlurId && !appState.isPlaying) return;
      if (!obj.enabled) return;
      const startT = obj.startTime ?? 0.0;
      const endT = (obj.endTime !== undefined && obj.endTime > 0) ? obj.endTime : 999999;
      if (time < startT || (endT < 90000 && time > endT)) return;

      const cur = interpolateBlurAtTime(obj, time);
      const itemEl = document.createElement("div");
      itemEl.className = `blur-rendered-item shape-${obj.shape || "rounded_rect"}`;
      itemEl.style.left = `${(cur.x * 100).toFixed(2)}%`;
      itemEl.style.top = `${(cur.y * 100).toFixed(2)}%`;
      itemEl.style.width = `${(cur.width * 100).toFixed(2)}%`;
      itemEl.style.height = `${(cur.height * 100).toFixed(2)}%`;
      itemEl.style.transform = `rotate(${cur.rotation || 0}deg)`;
      itemEl.style.opacity = `${(cur.opacity ?? 100) / 100}`;

      const pxBlur = Math.max(4, (cur.strength || 50) * 0.4);
      if (obj.blurType === "pixelate") {
        itemEl.style.backdropFilter = "blur(1.5px) contrast(180%)";
        itemEl.style.webkitBackdropFilter = "blur(1.5px) contrast(180%)";
      } else {
        itemEl.style.backdropFilter = `blur(${pxBlur.toFixed(1)}px)`;
        itemEl.style.webkitBackdropFilter = `blur(${pxBlur.toFixed(1)}px)`;
      }

      if (obj.feather && obj.feather > 0) {
        const mask = `radial-gradient(ellipse at center, black calc(100% - ${obj.feather}%), transparent 100%)`;
        itemEl.style.maskImage = mask;
        itemEl.style.webkitMaskImage = mask;
      } else {
        itemEl.style.maskImage = "none";
        itemEl.style.webkitMaskImage = "none";
      }

      itemEl.title = `Click to edit: ${obj.name}`;
      itemEl.addEventListener("pointerdown", (e) => {
        e.stopPropagation();
      });
      itemEl.addEventListener("click", (e) => {
        e.stopPropagation();
        selectBlurObject(obj.id);
      });

      ui.blurRenderedItemsLayer.appendChild(itemEl);
    });
  }

  // Active object interactive box
  if (ui.blurMaskBox) {
    const startT = activeObj?.startTime ?? 0.0;
    const endT = (activeObj?.endTime !== undefined && activeObj.endTime > 0) ? activeObj.endTime : 999999;
    if (!activeObj || !activeObj.enabled || time < startT || (endT < 90000 && time > endT) || appState.isPlaying) {
      ui.blurMaskBox.style.display = "none";
    } else {
      ui.blurMaskBox.style.display = "block";
      const cur = interpolateBlurAtTime(activeObj, time);

      ui.blurMaskBox.style.left = `${(cur.x * 100).toFixed(2)}%`;
      ui.blurMaskBox.style.top = `${(cur.y * 100).toFixed(2)}%`;
      ui.blurMaskBox.style.width = `${(cur.width * 100).toFixed(2)}%`;
      ui.blurMaskBox.style.height = `${(cur.height * 100).toFixed(2)}%`;
      ui.blurMaskBox.style.transform = `rotate(${cur.rotation || 0}deg)`;

      // Shape classes
      ui.blurMaskBox.classList.remove("shape-rectangle", "shape-rounded_rect", "shape-circle", "shape-ellipse", "shape-freeform");
      ui.blurMaskBox.classList.add(`shape-${activeObj.shape || "rounded_rect"}`);

      // Glass filter
      const pxBlur = Math.max(4, (cur.strength || 50) * 0.4);
      if (activeObj.blurType === "pixelate") {
        ui.blurMaskBox.style.backdropFilter = "blur(1.5px) contrast(180%)";
        ui.blurMaskBox.style.webkitBackdropFilter = "blur(1.5px) contrast(180%)";
        if (ui.blurMaskGlass) {
          ui.blurMaskGlass.style.backdropFilter = "blur(1.5px) contrast(180%)";
          ui.blurMaskGlass.style.webkitBackdropFilter = "blur(1.5px) contrast(180%)";
        }
      } else {
        ui.blurMaskBox.style.backdropFilter = `blur(${pxBlur.toFixed(1)}px)`;
        ui.blurMaskBox.style.webkitBackdropFilter = `blur(${pxBlur.toFixed(1)}px)`;
        if (ui.blurMaskGlass) {
          ui.blurMaskGlass.style.backdropFilter = `blur(${pxBlur.toFixed(1)}px)`;
          ui.blurMaskGlass.style.webkitBackdropFilter = `blur(${pxBlur.toFixed(1)}px)`;
        }
      }

      if (ui.blurMaskGlass) {
        ui.blurMaskGlass.style.opacity = `${(cur.opacity ?? 100) / 100}`;

        if (activeObj.feather && activeObj.feather > 0) {
          const mask = `radial-gradient(ellipse at center, black calc(100% - ${activeObj.feather}%), transparent 100%)`;
          ui.blurMaskGlass.style.maskImage = mask;
          ui.blurMaskGlass.style.webkitMaskImage = mask;
          ui.blurMaskBox.style.maskImage = mask;
          ui.blurMaskBox.style.webkitMaskImage = mask;
        } else {
          ui.blurMaskGlass.style.maskImage = "none";
          ui.blurMaskGlass.style.webkitMaskImage = "none";
          ui.blurMaskBox.style.maskImage = "none";
          ui.blurMaskBox.style.webkitMaskImage = "none";
        }
      }

      if (ui.blurActiveName) ui.blurActiveName.textContent = activeObj.name;
      if (ui.blurMaskCoordsBadge) {
        ui.blurMaskCoordsBadge.textContent = `X:${Math.round(cur.x * 100)}% Y:${Math.round(cur.y * 100)}% | ${Math.round(cur.width * 100)}%×${Math.round(cur.height * 100)}%`;
      }
    }
  }

  // Background Blur mode handling on blurBgCanvas with Subject Protection
  const bgObj = appState.blurStudio.objects.find((o) => o.enabled && o.blurType === "background" && time >= o.startTime && time <= o.endTime);
  if (ui.blurBgCanvas) {
    if (bgObj) {
      ui.blurBgCanvas.classList.remove("hidden");
      ui.blurBgCanvas.style.display = "block";
      const bgBlur = Math.max(4, (bgObj.strength || 50) * 0.4);
      const protectPct = bgObj.subjectProtection ?? 70;
      ui.blurBgCanvas.style.backdropFilter = `blur(${bgBlur.toFixed(1)}px)`;
      ui.blurBgCanvas.style.webkitBackdropFilter = `blur(${bgBlur.toFixed(1)}px)`;
      // Center subject cutout mask: keep foreground person sharp
      const maskGradient = `radial-gradient(ellipse 35% 45% at 50% 50%, transparent ${Math.max(10, protectPct - 20)}%, black ${protectPct}%)`;
      ui.blurBgCanvas.style.maskImage = maskGradient;
      ui.blurBgCanvas.style.webkitMaskImage = maskGradient;
    } else {
      ui.blurBgCanvas.classList.add("hidden");
      ui.blurBgCanvas.style.display = "none";
    }
  }

  // Keyframe status indicator
  if (activeObj && ui.btnToggleKeyframe) {
    const hasKfAtTime = activeObj.keyframes?.some((kf) => Math.abs(kf.time - time) < 0.15);
    if (ui.labelKeyframeToggle) {
      ui.labelKeyframeToggle.textContent = hasKfAtTime ? "Del KF" : "Add KF";
    }
    if (ui.iconCurrentKeyframe) {
      ui.iconCurrentKeyframe.style.fill = hasKfAtTime ? "var(--accent-primary, #6366f1)" : "none";
    }
    if (ui.blurKeyframeCount) {
      ui.blurKeyframeCount.textContent = `${activeObj.keyframes?.length || 0} KF`;
    }
  }
}

function selectBlurObject(id) {
  if (!id) {
    deselectBlurObject(false);
    return;
  }
  appState.blurStudio.activeBlurId = id;
  const obj = appState.blurStudio.objects?.find((o) => o.id === id);
  if (obj) {
    syncBlurControlsFromObject(obj);
  }
  renderBlurLayersList();
  renderTimelineBlurBlocks();
  updateBlurPreview(appState.currentTime);
}

function renderBlurLayersList() {
  if (!ui.blurLayersList) return;
  ui.blurLayersList.innerHTML = "";

  const objs = appState.blurStudio.objects || [];
  if (ui.blurLayersCount) {
    ui.blurLayersCount.textContent = `${objs.length} layer${objs.length === 1 ? "" : "s"}`;
  }

  objs.forEach((obj, idx) => {
    const item = document.createElement("div");
    item.className = `blur-layer-item ${obj.id === appState.blurStudio.activeBlurId ? "active" : ""}`;
    item.innerHTML = `
      <div class="layer-item-left">
        <button type="button" class="btn-layer-vis" title="${obj.enabled ? "Hide layer" : "Show layer"}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            ${obj.enabled
        ? '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'
        : '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'
      }
          </svg>
        </button>
        <button type="button" class="btn-layer-lock" title="${obj.locked ? "Unlock layer" : "Lock layer"}">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            ${obj.locked
        ? '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
        : '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>'
      }
          </svg>
        </button>
        <span class="layer-title" title="Click to select, double click to rename">${escapeHtml(obj.name)}</span>
      </div>
      <div class="layer-item-right">
        <span class="layer-type-badge">${escapeHtml(obj.blurType || "gaussian")}</span>
        <button type="button" class="btn-layer-dup" title="Duplicate layer">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
        </button>
        <button type="button" class="btn-layer-del" title="Delete layer">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>
    `;

    // Click selects layer
    item.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      selectBlurObject(obj.id);
    });

    // Double click to rename
    const titleEl = item.querySelector(".layer-title");
    titleEl.addEventListener("dblclick", () => {
      const newName = prompt("Rename blur layer:", obj.name);
      if (newName && newName.trim()) {
        pushBlurHistory();
        obj.name = newName.trim();
        renderBlurLayersList();
        renderTimelineBlurBlocks();
        updateBlurPreview(appState.currentTime);
      }
    });

    // Visibility toggle
    item.querySelector(".btn-layer-vis").addEventListener("click", (e) => {
      e.stopPropagation();
      pushBlurHistory();
      obj.enabled = !obj.enabled;
      renderBlurLayersList();
      updateBlurPreview(appState.currentTime);
    });

    // Lock toggle
    item.querySelector(".btn-layer-lock").addEventListener("click", (e) => {
      e.stopPropagation();
      pushBlurHistory();
      obj.locked = !obj.locked;
      renderBlurLayersList();
    });

    // Duplicate
    item.querySelector(".btn-layer-dup").addEventListener("click", (e) => {
      e.stopPropagation();
      duplicateBlurObject(obj.id);
    });

    // Delete
    item.querySelector(".btn-layer-del").addEventListener("click", (e) => {
      e.stopPropagation();
      deleteBlurObject(obj.id);
    });

    ui.blurLayersList.appendChild(item);
  });
}

function renderTimelineBlurBlocks() {
  if (!ui.timelineBlurBlocksContainer) return;
  ui.timelineBlurBlocksContainer.innerHTML = "";

  const totalDur = appState.duration > 0 ? appState.duration : 30.0;
  const objs = appState.blurStudio.objects || [];

  objs.forEach((obj) => {
    const startSec = Math.max(0, obj.startTime ?? 0);
    const endSec = Math.min(totalDur, obj.endTime ?? totalDur);
    const leftPct = (startSec / totalDur) * 100;
    const widthPct = Math.max(0.5, ((endSec - startSec) / totalDur) * 100);

    const block = document.createElement("div");
    block.className = `timeline-blur-block ${obj.id === appState.blurStudio.activeBlurId ? "active" : ""}`;
    block.style.left = `${leftPct.toFixed(2)}%`;
    block.style.width = `${widthPct.toFixed(2)}%`;
    block.dataset.id = obj.id;

    block.innerHTML = `
      <div class="timeline-trim-handle trim-left" title="Drag to trim start"></div>
      <span class="timeline-blur-block-title">${escapeHtml(obj.name)}</span>
      <div class="timeline-trim-handle trim-right" title="Drag to trim end"></div>
    `;

    // Render Keyframe markers
    if (obj.keyframes && obj.keyframes.length > 0 && endSec > startSec) {
      obj.keyframes.forEach((kf) => {
        if (kf.time >= startSec && kf.time <= endSec) {
          const kfPct = ((kf.time - startSec) / (endSec - startSec)) * 100;
          const pip = document.createElement("span");
          pip.className = "timeline-keyframe-pip";
          pip.style.left = `${kfPct.toFixed(1)}%`;
          pip.title = `Keyframe at ${kf.time.toFixed(2)}s`;
          pip.addEventListener("click", (e) => {
            e.stopPropagation();
            seekToTime(kf.time);
          });
          block.appendChild(pip);
        }
      });
    }

    // Select on click
    block.addEventListener("click", (e) => {
      if (e.target.closest(".timeline-trim-handle") || e.target.closest(".timeline-keyframe-pip")) return;
      selectBlurObject(obj.id);
    });

    // Handle block dragging / trimming
    bindTimelineBlockInteractions(block, obj, totalDur);

    ui.timelineBlurBlocksContainer.appendChild(block);
  });
}

function bindTimelineBlockInteractions(blockEl, obj, totalDur) {
  let mode = null; // 'move', 'trim-left', 'trim-right'
  let startClientX = 0;
  let initialStart = 0;
  let initialEnd = 0;

  function onPointerDown(e) {
    if (e.button !== undefined && e.button !== 0) return;
    const trimLeft = e.target.closest(".trim-left");
    const trimRight = e.target.closest(".trim-right");
    if (trimLeft) mode = "trim-left";
    else if (trimRight) mode = "trim-right";
    else mode = "move";

    selectBlurObject(obj.id);
    startClientX = e.clientX;
    initialStart = obj.startTime ?? 0;
    initialEnd = obj.endTime ?? totalDur;

    e.stopPropagation();
    e.preventDefault();

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  }

  function onPointerMove(e) {
    if (!mode) return;
    const containerRect = ui.timelineBlurBlocksContainer.getBoundingClientRect();
    if (!containerRect.width) return;

    const deltaSec = ((e.clientX - startClientX) / containerRect.width) * totalDur;
    const minSpan = 0.5;

    if (mode === "move") {
      const span = initialEnd - initialStart;
      let newStart = Math.max(0, Math.min(totalDur - span, initialStart + deltaSec));
      obj.startTime = parseFloat(newStart.toFixed(2));
      obj.endTime = parseFloat((newStart + span).toFixed(2));
    } else if (mode === "trim-left") {
      let newStart = Math.max(0, Math.min(initialEnd - minSpan, initialStart + deltaSec));
      obj.startTime = parseFloat(newStart.toFixed(2));
    } else if (mode === "trim-right") {
      let newEnd = Math.max(initialStart + minSpan, Math.min(totalDur, initialEnd + deltaSec));
      obj.endTime = parseFloat(newEnd.toFixed(2));
    }

    renderTimelineBlurBlocks();
    updateBlurPreview(appState.currentTime);
  }

  function onPointerUp() {
    if (mode) {
      pushBlurHistory();
      mode = null;
    }
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
  }

  blockEl.addEventListener("pointerdown", onPointerDown);
}

function syncBlurControlsFromObject(obj) {
  if (!obj) return;

  if (ui.selectBlurType) ui.selectBlurType.value = obj.blurType || "gaussian";
  if (ui.rangeBlurStrength) {
    ui.rangeBlurStrength.value = obj.strength ?? 50;
    if (ui.valBlurStrength) ui.valBlurStrength.textContent = `${obj.strength ?? 50}px`;
  }
  if (ui.rangeBlurFeather) {
    ui.rangeBlurFeather.value = obj.feather ?? 0;
    if (ui.valBlurFeather) ui.valBlurFeather.textContent = `${obj.feather ?? 0}%`;
  }
  if (ui.rangeBlurOpacity) {
    ui.rangeBlurOpacity.value = obj.opacity ?? 100;
    if (ui.valBlurOpacity) ui.valBlurOpacity.textContent = `${obj.opacity ?? 100}%`;
  }
  if (ui.rangeBlurRotation) {
    ui.rangeBlurRotation.value = obj.rotation ?? 0;
    if (ui.valBlurRotation) ui.valBlurRotation.textContent = `${obj.rotation ?? 0}°`;
  }
  if (ui.rangeBlurXPos) {
    ui.rangeBlurXPos.value = Math.round((obj.x ?? 0.3) * 100);
    if (ui.valBlurXPos) ui.valBlurXPos.textContent = `${Math.round((obj.x ?? 0.3) * 100)}%`;
  }
  if (ui.rangeBlurYPos) {
    ui.rangeBlurYPos.value = Math.round((obj.y ?? 0.2) * 100);
    if (ui.valBlurYPos) ui.valBlurYPos.textContent = `${Math.round((obj.y ?? 0.2) * 100)}%`;
  }
  if (ui.rangeBlurWidth) {
    ui.rangeBlurWidth.value = Math.round((obj.width ?? 0.4) * 100);
    if (ui.valBlurWidth) ui.valBlurWidth.textContent = `${Math.round((obj.width ?? 0.4) * 100)}%`;
  }
  if (ui.rangeBlurHeight) {
    ui.rangeBlurHeight.value = Math.round((obj.height ?? 0.25) * 100);
    if (ui.valBlurHeight) ui.valBlurHeight.textContent = `${Math.round((obj.height ?? 0.25) * 100)}%`;
  }

  // Background Blur Subject Protection Slider
  if (ui.fieldSubjectProtection) {
    if (obj.blurType === "background") {
      ui.fieldSubjectProtection.classList.remove("hidden");
      if (ui.rangeBlurSubjectProtect) {
        ui.rangeBlurSubjectProtect.value = obj.subjectProtection ?? 70;
        if (ui.valBlurSubjectProtect) ui.valBlurSubjectProtect.textContent = `${obj.subjectProtection ?? 70}%`;
      }
    } else {
      ui.fieldSubjectProtection.classList.add("hidden");
    }
  }

  // Update shape selector active button
  if (ui.blurShapeSelector) {
    ui.blurShapeSelector.querySelectorAll(".btn-shape, .shape-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.shape === (obj.shape || "rounded_rect"));
    });
  }

  // Keep legacy blurSettings aligned
  appState.blurSettings.x = obj.x;
  appState.blurSettings.y = obj.y;
  appState.blurSettings.w = obj.width;
  appState.blurSettings.h = obj.height;
  appState.blurSettings.strength = obj.strength;
}

function addNewBlurObject(customProps = {}) {
  pushBlurHistory();
  const nextIdx = appState.blurStudio.objects.length + 1;
  const newObj = {
    id: `blur_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
    name: customProps.name || `Blur #${nextIdx}`,
    enabled: true,
    locked: false,
    blurType: customProps.blurType || "gaussian",
    shape: customProps.shape || "rounded_rect",
    strength: customProps.strength ?? 55,
    feather: customProps.feather ?? 10,
    opacity: customProps.opacity ?? 100,
    rotation: customProps.rotation ?? 0,
    subjectProtection: customProps.subjectProtection ?? 70,
    x: customProps.x ?? 0.10,
    y: customProps.y ?? 0.72,
    width: customProps.width ?? 0.80,
    height: customProps.height ?? 0.22,
    startTime: customProps.startTime ?? 0.0,
    endTime: customProps.endTime ?? 999999,
    keyframes: customProps.keyframes || [],
  };

  appState.blurStudio.objects.push(newObj);
  appState.blurStudio.activeBlurId = newObj.id;
  setBlurStudioEnabled(true);
  syncBlurControlsFromObject(newObj);
  renderBlurLayersList();
  renderTimelineBlurBlocks();
  updateBlurPreview(appState.currentTime);
  showToast(`Added ${newObj.name}`);
}

function duplicateBlurObject(id) {
  const target = appState.blurStudio.objects.find((o) => o.id === id);
  if (!target) return;
  pushBlurHistory();
  const dup = JSON.parse(JSON.stringify(target));
  dup.id = `blur_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
  dup.name = `${target.name} (Copy)`;
  dup.x = Math.min(0.9, (dup.x || 0) + 0.05);
  dup.y = Math.min(0.9, (dup.y || 0) + 0.05);

  appState.blurStudio.objects.push(dup);
  selectBlurObject(dup.id);
  showToast(`Duplicated ${target.name}`);
}

function deleteBlurObject(id) {
  if (appState.blurStudio.objects.length <= 1) {
    // Reset to default instead of removing last
    resetActiveBlurObject();
    showToast("Reset layer to default");
    return;
  }
  pushBlurHistory();
  appState.blurStudio.objects = appState.blurStudio.objects.filter((o) => o.id !== id);
  const remaining = appState.blurStudio.objects[0];
  selectBlurObject(remaining.id);
  showToast("Deleted blur layer");
}

function resetActiveBlurObject() {
  const active = getActiveBlurObject();
  if (!active) return;
  pushBlurHistory();
  active.blurType = "gaussian";
  active.shape = "rounded_rect";
  active.strength = 55;
  active.feather = 10;
  active.opacity = 100;
  active.rotation = 0;
  active.x = 0.10;
  active.y = 0.72;
  active.width = 0.80;
  active.height = 0.22;
  active.startTime = 0.0;
  active.endTime = 999999;
  active.keyframes = [];
  syncBlurControlsFromObject(active);
  renderBlurLayersList();
  renderTimelineBlurBlocks();
  updateBlurPreview(appState.currentTime);
  showToast("Reset blur settings");
}

function toggleCurrentKeyframe() {
  const active = getActiveBlurObject();
  if (!active) return;
  pushBlurHistory();

  if (!active.keyframes) active.keyframes = [];
  const t = parseFloat(appState.currentTime.toFixed(2));
  const existingIdx = active.keyframes.findIndex((kf) => Math.abs(kf.time - t) < 0.15);

  if (existingIdx >= 0) {
    active.keyframes.splice(existingIdx, 1);
    showToast(`Removed keyframe at ${t}s`);
  } else {
    active.keyframes.push({
      time: t,
      x: active.x,
      y: active.y,
      width: active.width,
      height: active.height,
      rotation: active.rotation || 0,
      strength: active.strength,
      opacity: active.opacity ?? 100,
    });
    active.keyframes.sort((a, b) => a.time - b.time);
    showToast(`Added keyframe at ${t}s`);
  }

  renderTimelineBlurBlocks();
  updateBlurPreview(appState.currentTime);
}

function jumpKeyframe(direction) {
  const active = getActiveBlurObject();
  if (!active || !active.keyframes || active.keyframes.length === 0) {
    showToast("No keyframes found on active layer");
    return;
  }
  const t = appState.currentTime;
  const sorted = [...active.keyframes].sort((a, b) => a.time - b.time);

  if (direction < 0) {
    const prev = [...sorted].reverse().find((kf) => kf.time < t - 0.05);
    if (prev) seekToTime(prev.time);
    else seekToTime(sorted[0].time);
  } else {
    const next = sorted.find((kf) => kf.time > t + 0.05);
    if (next) seekToTime(next.time);
    else seekToTime(sorted[sorted.length - 1].time);
  }
}

function applyBlurPreset(preset) {
  const active = ensureActiveBlurObject();
  if (!active) return;
  pushBlurHistory();

  if (preset === "soft") {
    active.blurType = "gaussian";
    active.strength = 30;
    active.feather = 25;
    active.opacity = 100;
  } else if (preset === "medium") {
    active.blurType = "gaussian";
    active.strength = 55;
    active.feather = 15;
    active.opacity = 100;
  } else if (preset === "strong") {
    active.blurType = "gaussian";
    active.strength = 85;
    active.feather = 10;
    active.opacity = 100;
  } else if (preset === "privacy") {
    active.blurType = "pixelate";
    active.shape = "rectangle";
    active.strength = 75;
    active.feather = 0;
    active.opacity = 100;
  } else if (preset === "face") {
    active.blurType = "face";
    active.shape = "ellipse";
    active.strength = 60;
    active.feather = 30;
    active.width = 0.25;
    active.height = 0.28;
  } else if (preset === "mosaic") {
    active.blurType = "pixelate";
    active.shape = "rectangle";
    active.strength = 65;
    active.feather = 0;
  } else if (preset === "background") {
    active.blurType = "background";
    active.shape = "rectangle";
    active.x = 0.0;
    active.y = 0.0;
    active.width = 1.0;
    active.height = 1.0;
    active.strength = 45;
  } else if (preset === "full_width") {
    active.x = 0.0;
    active.width = 1.0;
  } else if (preset === "bottom_banner") {
    active.x = 0.0;
    active.y = 0.76;
    active.width = 1.0;
    active.height = 0.20;
    active.blurType = "gaussian";
    active.shape = "rectangle";
    active.strength = 55;
    active.feather = 0;
  }

  syncBlurControlsFromObject(active);
  renderBlurLayersList();
  updateBlurPreview(appState.currentTime);
  showToast(`Applied preset: ${preset}`);
}

function setBlurStudioEnabled(enabled) {
  appState.blurStudio.enabled = Boolean(enabled);
  appState.blurSettings.enabled = Boolean(enabled);

  if (ui.chkBlurSubtitles) ui.chkBlurSubtitles.checked = Boolean(enabled);
  if (ui.btnToggleBlurPreview) ui.btnToggleBlurPreview.classList.toggle("active-toggle", Boolean(enabled));
  if (ui.btnToolbarBlur) ui.btnToolbarBlur.classList.toggle("active-tool", Boolean(enabled));
  if (ui.btnSideToolbarBlur) ui.btnSideToolbarBlur.classList.toggle("active-tool", Boolean(enabled));
  document.body.classList.toggle("blur-studio-active", Boolean(enabled));
  if (ui.playerAspectWrapper) ui.playerAspectWrapper.classList.toggle("blur-active", Boolean(enabled));

  if (enabled) {
    // Ensure tab is on Voice & Video Canvas where the blur controls live
    if (appState.activeStudioTab !== "voice") {
      switchStudioTab("voice");
    }
    if (ui.blurSubpanel) {
      ui.blurSubpanel.classList.remove("hidden");
      ui.blurSubpanel.style.display = "flex";
    }
    if (ui.timelineBlurTrackRow) {
      ui.timelineBlurTrackRow.classList.remove("hidden");
      ui.timelineBlurTrackRow.style.display = "flex";
    }
    if (!appState.blurStudio.objects || appState.blurStudio.objects.length === 0) {
      appState.blurStudio.objects = [
        {
          id: "blur_1",
          name: "Blur #1 - Subtitle Mask",
          enabled: true,
          locked: false,
          blurType: "gaussian",
          shape: "rounded_rect",
          strength: 55,
          feather: 10,
          opacity: 100,
          rotation: 0,
          x: 0.10,
          y: 0.72,
          width: 0.80,
          height: 0.22,
          startTime: 0.0,
          endTime: 999999,
          keyframes: [],
        },
      ];
    } else {
      appState.blurStudio.objects.forEach((o) => {
        if (!o.endTime || o.endTime < 90000) {
          o.endTime = 999999;
        }
      });
    }

    if (!appState.blurStudio.activeBlurId || !appState.blurStudio.objects.some(o => o.id === appState.blurStudio.activeBlurId)) {
      appState.blurStudio.activeBlurId = appState.blurStudio.objects[0].id;
    }
    const active = getActiveBlurObject();
    if (active) syncBlurControlsFromObject(active);
    renderBlurLayersList();
    renderTimelineBlurBlocks();
  } else {
    deselectBlurObject(true);
    if (ui.blurSubpanel) {
      ui.blurSubpanel.classList.add("hidden");
      ui.blurSubpanel.style.display = "none";
    }
    if (ui.timelineBlurTrackRow) {
      ui.timelineBlurTrackRow.classList.add("hidden");
      ui.timelineBlurTrackRow.style.display = "none";
    }
  }

  syncOverlayToVideo();
  updateBlurPreview(appState.currentTime);
}

function setCanvasAspectRatio(ratio) {
  appState.blurSettings.aspectRatio = ratio;
  if (!ui.playerAspectWrapper) return;
  ui.playerAspectWrapper.classList.remove("aspect-9-16", "aspect-1-1", "aspect-4-5", "aspect-original");
  if (ratio === "9:16") {
    ui.playerAspectWrapper.classList.add("aspect-9-16");
    showToast("9:16 Vertical Canvas (TikTok / Reels / Shorts with Blurred Canvas)");
  } else if (ratio === "1:1") {
    ui.playerAspectWrapper.classList.add("aspect-1-1");
    showToast("1:1 Square Canvas (Instagram / Facebook with Blurred Canvas)");
  } else if (ratio === "4:5") {
    ui.playerAspectWrapper.classList.add("aspect-4-5");
    showToast("4:5 Portrait Canvas (Instagram / Facebook Feed with Blurred Canvas)");
  } else {
    ui.playerAspectWrapper.classList.add("aspect-original");
    if (ui.mainVideoPlayer && ui.mainVideoPlayer.videoWidth && ui.mainVideoPlayer.videoHeight) {
      const vw = ui.mainVideoPlayer.videoWidth;
      const vh = ui.mainVideoPlayer.videoHeight;
      if (vw / vh < 0.75) {
        ui.playerAspectWrapper.classList.add("aspect-9-16");
      } else if (Math.abs(vw / vh - 1.0) < 0.15) {
        ui.playerAspectWrapper.classList.add("aspect-1-1");
      } else if (vw / vh < 0.95) {
        ui.playerAspectWrapper.classList.add("aspect-4-5");
      }
    }
    showToast("Original Source Format");
  }
  syncOverlayToVideo();
  updateBlurPreview(appState.currentTime);
}

// Direct Interactive Dragging, 8-way Resizing & Rotation
function initBlurDirectManipulation() {
  if (!ui.blurMaskBox || !ui.playerAspectWrapper) return;

  let dragMode = null; // 'box', 'rotate', 'nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'
  let startX = 0;
  let startY = 0;
  let startBoxX = 0;
  let startBoxY = 0;
  let startBoxW = 0;
  let startBoxH = 0;
  let startRotation = 0;
  let boxCenter = { x: 0, y: 0 };

  function onPointerDown(e) {
    if (e.button !== undefined && e.button !== 0) return;
    const active = getActiveBlurObject();
    if (!active || active.locked) return;

    const rotHandle = e.target.closest(".blur-rotation-handle");
    const resHandle = e.target.closest(".blur-mask-handle");

    if (rotHandle) {
      dragMode = "rotate";
      const rect = ui.blurMaskBox.getBoundingClientRect();
      boxCenter = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
      startRotation = active.rotation || 0;
    } else if (resHandle && resHandle.dataset.handle) {
      dragMode = resHandle.dataset.handle;
    } else {
      dragMode = "box";
    }

    startX = e.clientX;
    startY = e.clientY;
    startBoxX = active.x ?? 0.3;
    startBoxY = active.y ?? 0.2;
    startBoxW = active.width ?? 0.4;
    startBoxH = active.height ?? 0.25;

    e.stopPropagation();
    e.preventDefault();

    document.body.classList.add("blur-mask-resizing");
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
  }

  function onPointerMove(e) {
    if (!dragMode) return;
    const active = getActiveBlurObject();
    if (!active || active.locked) return;

    const overlayRect = ui.videoBlurMultiOverlay ? ui.videoBlurMultiOverlay.getBoundingClientRect() : ui.playerAspectWrapper.getBoundingClientRect();
    if (!overlayRect.width || !overlayRect.height) return;

    if (dragMode === "rotate") {
      const angleRad = Math.atan2(e.clientY - boxCenter.y, e.clientX - boxCenter.x);
      let deg = Math.round((angleRad * 180) / Math.PI) + 90;
      if (deg > 180) deg -= 360;
      if (deg < -180) deg += 360;
      active.rotation = deg;
      if (ui.rangeBlurRotation) ui.rangeBlurRotation.value = deg;
      if (ui.valBlurRotation) ui.valBlurRotation.textContent = `${deg}°`;
      updateBlurPreview(appState.currentTime);
      return;
    }

    const deltaX = (e.clientX - startX) / overlayRect.width;
    const deltaY = (e.clientY - startY) / overlayRect.height;
    const minW = 0.03;
    const minH = 0.02;

    if (dragMode === "box") {
      const maxW = startBoxW;
      const maxH = startBoxH;
      let newX = Math.max(0, Math.min(1 - maxW, startBoxX + deltaX));
      let newY = Math.max(0, Math.min(1 - maxH, startBoxY + deltaY));
      // Edge snapping
      if (newX < 0.025) newX = 0;
      if (1.0 - (newX + maxW) < 0.025) newX = 1.0 - maxW;
      if (newY < 0.025) newY = 0;
      if (1.0 - (newY + maxH) < 0.025) newY = 1.0 - maxH;

      active.x = parseFloat(newX.toFixed(3));
      active.y = parseFloat(newY.toFixed(3));
    } else {
      let x = startBoxX;
      let y = startBoxY;
      let w = startBoxW;
      let h = startBoxH;

      // Horizontal resizing
      if (dragMode.includes("w") && dragMode !== "sw" && dragMode !== "nw") {
        const maxLeft = startBoxX + startBoxW - minW;
        const newX = Math.max(0, Math.min(maxLeft, startBoxX + deltaX));
        w = (startBoxX + startBoxW) - newX;
        x = newX;
      } else if (dragMode === "nw" || dragMode === "sw") {
        const maxLeft = startBoxX + startBoxW - minW;
        const newX = Math.max(0, Math.min(maxLeft, startBoxX + deltaX));
        w = (startBoxX + startBoxW) - newX;
        x = newX;
      } else if (dragMode.includes("e")) {
        w = Math.max(minW, Math.min(1.0 - startBoxX, startBoxW + deltaX));
      }

      // Vertical resizing
      if (dragMode.includes("n")) {
        const maxTop = startBoxY + startBoxH - minH;
        const newY = Math.max(0, Math.min(maxTop, startBoxY + deltaY));
        h = (startBoxY + startBoxH) - newY;
        y = newY;
      } else if (dragMode.includes("s")) {
        h = Math.max(minH, Math.min(1.0 - startBoxY, startBoxH + deltaY));
      }

      // Edge snapping for resizing handles
      if (x < 0.025) {
        w = w + x;
        x = 0;
      }
      if (1.0 - (x + w) < 0.025) {
        w = 1.0 - x;
      }
      if (y < 0.025) {
        h = h + y;
        y = 0;
      }
      if (1.0 - (y + h) < 0.025) {
        h = 1.0 - y;
      }

      active.x = parseFloat(Math.max(0, Math.min(0.98, x)).toFixed(3));
      active.y = parseFloat(Math.max(0, Math.min(0.98, y)).toFixed(3));
      active.width = parseFloat(Math.max(minW, Math.min(1.0 - active.x, w)).toFixed(3));
      active.height = parseFloat(Math.max(minH, Math.min(1.0 - active.y, h)).toFixed(3));
    }

    // Sync sliders
    if (ui.rangeBlurXPos) {
      ui.rangeBlurXPos.value = Math.round(active.x * 100);
      if (ui.valBlurXPos) ui.valBlurXPos.textContent = `${Math.round(active.x * 100)}%`;
    }
    if (ui.rangeBlurYPos) {
      ui.rangeBlurYPos.value = Math.round(active.y * 100);
      if (ui.valBlurYPos) ui.valBlurYPos.textContent = `${Math.round(active.y * 100)}%`;
    }
    if (ui.rangeBlurWidth) {
      ui.rangeBlurWidth.value = Math.round(active.width * 100);
      if (ui.valBlurWidth) ui.valBlurWidth.textContent = `${Math.round(active.width * 100)}%`;
    }
    if (ui.rangeBlurHeight) {
      ui.rangeBlurHeight.value = Math.round(active.height * 100);
      if (ui.valBlurHeight) ui.valBlurHeight.textContent = `${Math.round(active.height * 100)}%`;
    }

    // Also update current keyframe if playhead is on one
    if (active.keyframes && active.keyframes.length > 0) {
      const kf = active.keyframes.find((k) => Math.abs(k.time - appState.currentTime) < 0.15);
      if (kf) {
        kf.x = active.x;
        kf.y = active.y;
        kf.width = active.width;
        kf.height = active.height;
      }
    }

    updateBlurPreview(appState.currentTime);
  }

  function onPointerUp() {
    if (dragMode) {
      pushBlurHistory();
      dragMode = null;
    }
    document.body.classList.remove("blur-mask-resizing");
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    window.removeEventListener("pointercancel", onPointerUp);
  }

  ui.blurMaskBox.addEventListener("pointerdown", onPointerDown);

  // Auto-apply & Deselect only when switching to non-blur tools or clicking modal backdrops
  document.addEventListener("pointerdown", (e) => {
    if (!appState.blurStudio || !appState.blurStudio.activeBlurId || !appState.blurStudio.enabled) return;

    // Do NOT deselect if clicking inside video player area, controls, sidebar, or studio panels
    if (
      e.target.closest("#blurMaskBox") ||
      e.target.closest(".blur-rendered-item") ||
      e.target.closest("#blurSubpanel") ||
      e.target.closest(".blur-studio-container") ||
      e.target.closest(".blur-studio-subpanel") ||
      e.target.closest("#timelineBlurTrackRow") ||
      e.target.closest("#blurPresetChips") ||
      e.target.closest("#btnToolbarBlur") ||
      e.target.closest("#btnSideToolbarBlur") ||
      e.target.closest("#btnToggleBlurPreview") ||
      e.target.closest("#playerAspectWrapper") ||
      e.target.closest(".subpanel")
    ) {
      return;
    }
  });

  // Keyboard shortcut: Escape or Enter auto-applies and deselects
  window.addEventListener("keydown", (e) => {
    if ((e.key === "Escape" || e.key === "Enter") && appState.blurStudio && appState.blurStudio.activeBlurId) {
      if (document.activeElement && ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
        document.activeElement.blur();
      }
      deselectBlurObject(true);
    }
  });
}

// AI Face Detection API Call
async function detectFacesOnCurrentFrame() {
  if (!appState.sessionId) {
    showToast("Please upload a video first to detect faces.");
    return;
  }

  showToast("Detecting faces on video frame with AI...");
  if (ui.btnDetectFaces) ui.btnDetectFaces.disabled = true;

  try {
    const res = await fetch("/api/detect-faces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: appState.sessionId,
        current_time: appState.currentTime || 0.0,
        timestamp: appState.currentTime || 0.0,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Face detection failed");
    }

    const data = await res.json();
    const faces = data.faces || [];
    showToast(`Detected ${faces.length} face(s) on frame!`);

    if (ui.detectedFacesPills) {
      ui.detectedFacesPills.innerHTML = "";
      if (faces.length === 0) {
        ui.detectedFacesPills.innerHTML = '<span class="face-pill">No face detected</span>';
      } else {
        faces.forEach((face, idx) => {
          const pill = document.createElement("button");
          pill.type = "button";
          pill.className = "face-pill active-pill";
          pill.textContent = `+ Blur Face #${idx + 1} (${Math.round((face.confidence || 0.9) * 100)}%)`;
          pill.addEventListener("click", () => {
            addNewBlurObject({
              name: `Face #${idx + 1}`,
              blurType: "face",
              shape: "ellipse",
              strength: 65,
              feather: 30,
              x: face.x,
              y: face.y,
              width: face.width ?? face.w ?? 0.25,
              height: face.height ?? face.h ?? 0.28,
            });
          });
          ui.detectedFacesPills.appendChild(pill);
        });
      }
    }

    // Auto-apply if "Apply All" is clicked or user requested
    if (ui.btnApplyAllFaces) {
      ui.btnApplyAllFaces.onclick = () => {
        faces.forEach((f, i) => {
          addNewBlurObject({
            name: `Face #${i + 1}`,
            blurType: "face",
            shape: "ellipse",
            strength: 65,
            feather: 30,
            x: f.x,
            y: f.y,
            width: f.width ?? f.w ?? 0.25,
            height: f.height ?? f.h ?? 0.28,
          });
        });
        showToast(`Created blur layers for all ${faces.length} faces!`);
      };
    }
  } catch (err) {
    console.error("Detect faces error:", err);
    showToast(`Face detection: ${err.message}`);
  } finally {
    if (ui.btnDetectFaces) ui.btnDetectFaces.disabled = false;
  }
}

// Bind all Blur Studio Events
function bindBlurStudioEvents() {
  // Toolbar Blur Button
  if (ui.btnToolbarBlur) {
    ui.btnToolbarBlur.addEventListener("click", () => {
      openBlurStudioDialog();
      showToast("✨ Blur Studio Opened");
    });
  }

  // Left Editor Tools Sidebar Tool Switching
  if (ui.editorToolsSidebar) {
    ui.editorToolsSidebar.querySelectorAll(".btn-tool-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tool = btn.dataset.tool;
        ui.editorToolsSidebar.querySelectorAll(".btn-tool-item").forEach((b) => b.classList.remove("active", "active-tool"));
        btn.classList.add("active", "active-tool");
        const isEditingTool = tool && tool !== "select";
        document.body.classList.toggle("editing-tool-active", isEditingTool);
        if (tool === "blur") {
          openBlurStudioDialog();
          showToast("✨ Blur Studio Opened");
        } else if (tool === "subtitles") {
          switchStudioTab("subtitles");
          showToast("Subtitle Studio Opened");
        } else if (tool === "recap") {
          switchStudioTab("recap");
          showToast("Story Recap Studio Opened");
        } else {
          showToast(`Selected ${tool.toUpperCase()} Tool`);
        }
      });
    });
  }

  if (ui.btnToggleBlurPreview) {
    ui.btnToggleBlurPreview.addEventListener("click", () => {
      const next = !appState.blurStudio.enabled;
      setBlurStudioEnabled(next);
      const btn = ui.btnToggleBlurPreview;
      if (btn) btn.classList.toggle("active-tool", next);
      showToast(next ? "Blur preview ON" : "Blur preview OFF");
    });
  }

  // Backdrop click closes the dialog
  const blurModal = document.getElementById("blurStudioModal");
  if (blurModal) {
    blurModal.addEventListener("click", (e) => {
      if (e.target === blurModal) closeBlurStudioDialog();
    });
  }

  // Checkbox Subtitle / Watermark Blur
  if (ui.chkBlurSubtitles) {
    ui.chkBlurSubtitles.addEventListener("change", (e) => {
      setBlurStudioEnabled(e.target.checked);
    });
  }

  // Canvas format (Aspect ratio)
  if (ui.selectCanvasAspect) {
    ui.selectCanvasAspect.addEventListener("change", (e) => {
      setCanvasAspectRatio(e.target.value);
    });
  }

  // Add Blur Layer button
  if (ui.btnAddBlurObject) {
    ui.btnAddBlurObject.addEventListener("click", () => {
      addNewBlurObject();
    });
  }

  // Preset Chips
  if (ui.blurPresetChips) {
    ui.blurPresetChips.querySelectorAll(".preset-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        ui.blurPresetChips.querySelectorAll(".preset-chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        applyBlurPreset(chip.dataset.preset);
      });
    });
  }

  // Blur Type Selector
  if (ui.selectBlurType) {
    ui.selectBlurType.addEventListener("change", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      pushBlurHistory();
      active.blurType = e.target.value;
      if (ui.fieldSubjectProtection) {
        if (e.target.value === "background") {
          ui.fieldSubjectProtection.classList.remove("hidden");
        } else {
          ui.fieldSubjectProtection.classList.add("hidden");
        }
      }
      renderBlurLayersList();
      updateBlurPreview(appState.currentTime);
    });
  }

  // Shape Selector Buttons
  if (ui.blurShapeSelector) {
    ui.blurShapeSelector.querySelectorAll(".btn-shape, .shape-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const active = ensureActiveBlurObject();
        if (!active) return;
        pushBlurHistory();
        active.shape = btn.dataset.shape;
        ui.blurShapeSelector.querySelectorAll(".btn-shape, .shape-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        updateBlurPreview(appState.currentTime);
      });
    });
  }

  // Sliders: Strength, Feather, Opacity, Rotation
  if (ui.rangeBlurStrength) {
    ui.rangeBlurStrength.addEventListener("input", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      const val = parseInt(e.target.value);
      active.strength = val;
      if (ui.valBlurStrength) ui.valBlurStrength.textContent = `${val}px`;
      updateBlurPreview(appState.currentTime);
    });
    ui.rangeBlurStrength.addEventListener("change", () => pushBlurHistory());
  }

  if (ui.rangeBlurFeather) {
    ui.rangeBlurFeather.addEventListener("input", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      const val = parseInt(e.target.value);
      active.feather = val;
      if (ui.valBlurFeather) ui.valBlurFeather.textContent = `${val}%`;
      updateBlurPreview(appState.currentTime);
    });
    ui.rangeBlurFeather.addEventListener("change", () => pushBlurHistory());
  }

  if (ui.rangeBlurOpacity) {
    ui.rangeBlurOpacity.addEventListener("input", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      const val = parseInt(e.target.value);
      active.opacity = val;
      if (ui.valBlurOpacity) ui.valBlurOpacity.textContent = `${val}%`;
      updateBlurPreview(appState.currentTime);
    });
    ui.rangeBlurOpacity.addEventListener("change", () => pushBlurHistory());
  }

  if (ui.rangeBlurRotation) {
    ui.rangeBlurRotation.addEventListener("input", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      const val = parseInt(e.target.value);
      active.rotation = val;
      if (ui.valBlurRotation) ui.valBlurRotation.textContent = `${val}°`;
      updateBlurPreview(appState.currentTime);
    });
    ui.rangeBlurRotation.addEventListener("change", () => pushBlurHistory());
  }

  // Background Blur Subject Protection Slider
  if (ui.rangeBlurSubjectProtect) {
    ui.rangeBlurSubjectProtect.addEventListener("input", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      const val = parseInt(e.target.value);
      active.subjectProtection = val;
      if (ui.valBlurSubjectProtect) ui.valBlurSubjectProtect.textContent = `${val}%`;
      updateBlurPreview(appState.currentTime);
    });
    ui.rangeBlurSubjectProtect.addEventListener("change", () => pushBlurHistory());
  }

  // Sliders: Position and Size
  if (ui.rangeBlurXPos) {
    ui.rangeBlurXPos.addEventListener("input", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      active.x = parseInt(e.target.value) / 100;
      if (ui.valBlurXPos) ui.valBlurXPos.textContent = `${e.target.value}%`;
      updateBlurPreview(appState.currentTime);
    });
    ui.rangeBlurXPos.addEventListener("change", () => pushBlurHistory());
  }

  if (ui.rangeBlurYPos) {
    ui.rangeBlurYPos.addEventListener("input", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      active.y = parseInt(e.target.value) / 100;
      if (ui.valBlurYPos) ui.valBlurYPos.textContent = `${e.target.value}%`;
      updateBlurPreview(appState.currentTime);
    });
    ui.rangeBlurYPos.addEventListener("change", () => pushBlurHistory());
  }

  if (ui.rangeBlurWidth) {
    ui.rangeBlurWidth.addEventListener("input", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      active.width = parseInt(e.target.value) / 100;
      if (ui.valBlurWidth) ui.valBlurWidth.textContent = `${e.target.value}%`;
      updateBlurPreview(appState.currentTime);
    });
    ui.rangeBlurWidth.addEventListener("change", () => pushBlurHistory());
  }

  if (ui.rangeBlurHeight) {
    ui.rangeBlurHeight.addEventListener("input", (e) => {
      const active = ensureActiveBlurObject();
      if (!active) return;
      active.height = parseInt(e.target.value) / 100;
      if (ui.valBlurHeight) ui.valBlurHeight.textContent = `${e.target.value}%`;
      updateBlurPreview(appState.currentTime);
    });
    ui.rangeBlurHeight.addEventListener("change", () => pushBlurHistory());
  }

  // Keyframe controls
  if (ui.btnToggleKeyframe) {
    ui.btnToggleKeyframe.addEventListener("click", toggleCurrentKeyframe);
  }
  if (ui.btnPrevKeyframe) {
    ui.btnPrevKeyframe.addEventListener("click", () => jumpKeyframe(-1));
  }
  if (ui.btnNextKeyframe) {
    ui.btnNextKeyframe.addEventListener("click", () => jumpKeyframe(1));
  }

  // Actions: Duplicate, Reset, Delete
  if (ui.btnDuplicateBlur) {
    ui.btnDuplicateBlur.addEventListener("click", () => {
      const active = ensureActiveBlurObject();
      if (active) duplicateBlurObject(active.id);
    });
  }

  if (ui.btnResetBlur) {
    ui.btnResetBlur.addEventListener("click", resetActiveBlurObject);
  }

  if (ui.btnDeleteBlur) {
    ui.btnDeleteBlur.addEventListener("click", () => {
      const active = ensureActiveBlurObject();
      if (active) deleteBlurObject(active.id);
    });
  }

  // AI Auto Blur Mode Switching (Face Detection vs Object Tracking)
  if (ui.radioAiFace) {
    ui.radioAiFace.addEventListener("change", () => {
      if (ui.radioAiFace.checked) {
        if (ui.labelDetectAction) ui.labelDetectAction.textContent = "Detect Faces";
        document.querySelectorAll(".ai-mode-radios .radio-pill-item").forEach((p) => p.classList.remove("active-radio"));
        ui.radioAiFace.closest(".radio-pill-item")?.classList.add("active-radio");
      }
    });
  }

  if (ui.radioAiObject) {
    ui.radioAiObject.addEventListener("change", () => {
      if (ui.radioAiObject.checked) {
        if (ui.labelDetectAction) ui.labelDetectAction.textContent = "Track Object";
        document.querySelectorAll(".ai-mode-radios .radio-pill-item").forEach((p) => p.classList.remove("active-radio"));
        ui.radioAiObject.closest(".radio-pill-item")?.classList.add("active-radio");
      }
    });
  }

  // AI Face Detection / Object Tracking
  if (ui.btnDetectFaces) {
    ui.btnDetectFaces.addEventListener("click", () => {
      if (ui.radioAiObject && ui.radioAiObject.checked) {
        // Object tracking on current active blur region or center
        const active = getActiveBlurObject();
        if (active) {
          showToast(`Tracking ${active.name} across video frames...`);
        } else {
          showToast("Select or create a blur region to track object.");
        }
      } else {
        detectFacesOnCurrentFrame();
      }
    });
  }

  // Direct Interactive Dragging, Resizing, and Rotation on video player
  initBlurDirectManipulation();

  // Keyboard Shortcuts for Blur Studio
  document.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;

    // 'B' key toggles Blur Studio
    if (e.key === "b" || e.key === "B") {
      setBlurStudioEnabled(!appState.blurStudio.enabled);
    }

    // Ctrl+Z = Undo, Ctrl+Y / Ctrl+Shift+Z = Redo
    if (e.ctrlKey || e.metaKey) {
      if (e.key === "z" || e.key === "Z") {
        if (e.shiftKey) {
          e.preventDefault();
          redoBlur();
        } else {
          e.preventDefault();
          undoBlur();
        }
      } else if (e.key === "y" || e.key === "Y") {
        e.preventDefault();
        redoBlur();
      }
    }

    // Delete / Backspace key deletes active layer
    if (e.key === "Delete" && appState.blurStudio.enabled) {
      const active = getActiveBlurObject();
      if (active) {
        e.preventDefault();
        deleteBlurObject(active.id);
      }
    }
  });

  // Initial render of layers and blocks
  renderBlurLayersList();
  renderTimelineBlurBlocks();
}

function switchAudioTrack(track) {
  if (track === "dubbed") {
    if (!appState.dubbedVideoUrl) {
      showToast("Khmer dubbed video not yet generated. Click 'Generate Final Dubbed Video' below!");
      return;
    }
    appState.activeAudioTrack = "dubbed";
    ui.btnTrackDubbed.classList.add("active");
    ui.btnTrackOriginal.classList.remove("active");
    const isPlaying = !ui.mainVideoPlayer.paused;
    const currentTime = ui.mainVideoPlayer.currentTime;
    ui.mainVideoPlayer.src = appState.dubbedVideoUrl;
    ui.mainVideoPlayer.currentTime = currentTime;
    if (isPlaying) ui.mainVideoPlayer.play().catch(() => { });
    showToast("Switched to Khmer Dubbed Audio");
  } else {
    appState.activeAudioTrack = "original";
    ui.btnTrackOriginal.classList.add("active");
    ui.btnTrackDubbed.classList.remove("active");
    if (appState.videoUrl) {
      const isPlaying = !ui.mainVideoPlayer.paused;
      const currentTime = ui.mainVideoPlayer.currentTime;
      ui.mainVideoPlayer.src = appState.videoUrl;
      ui.mainVideoPlayer.currentTime = currentTime;
      if (isPlaying) ui.mainVideoPlayer.play().catch(() => { });
    }
    showToast("Switched to Original Audio");
  }
}


// ==========================================================================
// Subtitle Studio Engine & Presets
// ==========================================================================
const SUBTITLE_PRESETS = {
  classic: {
    fontFamily: "Kantumruy Pro",
    fontSize: 28,
    fontWeight: "700",
    italic: false,
    uppercase: false,
    letterSpacing: 0,
    lineHeight: 1.4,
    align: "center",
    textColor: "#ffffff",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 3,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 4,
    shadowOffsetX: 2,
    shadowOffsetY: 2,
    bgStyle: "semi",
    bgColor: "#000000",
    bgOpacity: 60,
    bgPadding: 8,
    bgRadius: 8,
    posX: 50,
    posY: 85,
    entranceAnim: "none",
    exitAnim: "none",
    wordAnim: "none",
  },
  youtube: {
    fontFamily: "Plus Jakarta Sans",
    fontSize: 32,
    fontWeight: "800",
    italic: false,
    uppercase: false,
    letterSpacing: 0.5,
    lineHeight: 1.3,
    align: "center",
    textColor: "#fde047",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 4,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 6,
    shadowOffsetX: 3,
    shadowOffsetY: 3,
    bgStyle: "none",
    bgColor: "#000000",
    bgOpacity: 0,
    bgPadding: 6,
    bgRadius: 6,
    posX: 50,
    posY: 85,
    entranceAnim: "pop",
    exitAnim: "none",
    wordAnim: "none",
  },
  tiktok: {
    fontFamily: "Kantumruy Pro",
    fontSize: 34,
    fontWeight: "800",
    italic: false,
    uppercase: false,
    letterSpacing: 0.5,
    lineHeight: 1.3,
    align: "center",
    textColor: "#ffffff",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 4,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 8,
    shadowOffsetX: 3,
    shadowOffsetY: 3,
    bgStyle: "none",
    bgColor: "#000000",
    bgOpacity: 0,
    bgPadding: 0,
    bgRadius: 0,
    posX: 50,
    posY: 75,
    entranceAnim: "pop",
    exitAnim: "scale",
    wordAnim: "highlightCurrent",
    karaokeColor: "#facc15",
  },
  tiktok_box: {
    fontFamily: "Kantumruy Pro",
    fontSize: 32,
    fontWeight: "800",
    italic: false,
    uppercase: false,
    letterSpacing: 0.5,
    lineHeight: 1.3,
    align: "center",
    textColor: "#ffffff",
    textOpacity: 100,
    strokeEnabled: false,
    strokeColor: "#000000",
    strokeWidth: 0,
    shadowEnabled: false,
    shadowColor: "#000000",
    shadowBlur: 0,
    shadowOffsetX: 0,
    shadowOffsetY: 0,
    bgStyle: "rounded",
    bgColor: "#000000",
    bgOpacity: 85,
    bgPadding: 12,
    bgRadius: 20,
    posX: 50,
    posY: 75,
    entranceAnim: "pop",
    exitAnim: "scale",
    wordAnim: "highlightCurrent",
    karaokeColor: "#38bdf8",
  },
  neon_pulse: {
    fontFamily: "Kantumruy Pro",
    fontSize: 34,
    fontWeight: "800",
    italic: false,
    uppercase: false,
    letterSpacing: 0.5,
    lineHeight: 1.3,
    align: "center",
    textColor: "#22d3ee",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 4,
    shadowEnabled: true,
    shadowColor: "#0891b2",
    shadowBlur: 14,
    shadowOffsetX: 0,
    shadowOffsetY: 2,
    bgStyle: "semi",
    bgColor: "#082f49",
    bgOpacity: 70,
    bgPadding: 10,
    bgRadius: 14,
    posX: 50,
    posY: 80,
    entranceAnim: "pop",
    exitAnim: "fadeOut",
    wordAnim: "highlightCurrent",
    karaokeColor: "#fef08a",
  },
  instagram: {
    fontFamily: "Plus Jakarta Sans",
    fontSize: 30,
    fontWeight: "700",
    italic: false,
    uppercase: false,
    letterSpacing: 0,
    lineHeight: 1.35,
    align: "center",
    textColor: "#ffffff",
    textOpacity: 100,
    strokeEnabled: false,
    strokeColor: "#000000",
    strokeWidth: 0,
    shadowEnabled: true,
    shadowColor: "#ec4899",
    shadowBlur: 10,
    shadowOffsetX: 0,
    shadowOffsetY: 3,
    bgStyle: "semi",
    bgColor: "#18181b",
    bgOpacity: 75,
    bgPadding: 10,
    bgRadius: 12,
    posX: 50,
    posY: 80,
    entranceAnim: "slideUp",
    exitAnim: "slideDown",
    wordAnim: "none",
  },
  podcast: {
    fontFamily: "Kantumruy Pro",
    fontSize: 26,
    fontWeight: "600",
    italic: false,
    uppercase: false,
    letterSpacing: 0,
    lineHeight: 1.4,
    align: "center",
    textColor: "#f3f4f6",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#111827",
    strokeWidth: 2,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 4,
    shadowOffsetX: 1,
    shadowOffsetY: 2,
    bgStyle: "solid",
    bgColor: "#1f2937",
    bgOpacity: 95,
    bgPadding: 10,
    bgRadius: 10,
    posX: 50,
    posY: 85,
    entranceAnim: "fadeIn",
    exitAnim: "fadeOut",
    wordAnim: "none",
  },
  cinema: {
    fontFamily: "Noto Serif Khmer",
    fontSize: 24,
    fontWeight: "400",
    italic: true,
    uppercase: false,
    letterSpacing: 1.5,
    lineHeight: 1.5,
    align: "center",
    textColor: "#fef08a",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 2,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 5,
    shadowOffsetX: 2,
    shadowOffsetY: 2,
    bgStyle: "none",
    bgColor: "#000000",
    bgOpacity: 0,
    bgPadding: 0,
    bgRadius: 0,
    posX: 50,
    posY: 88,
    entranceAnim: "none",
    exitAnim: "none",
    wordAnim: "none",
  },
  minimal: {
    fontFamily: "Inter",
    fontSize: 24,
    fontWeight: "500",
    italic: false,
    uppercase: false,
    letterSpacing: 0,
    lineHeight: 1.3,
    align: "center",
    textColor: "#ffffff",
    textOpacity: 100,
    strokeEnabled: false,
    strokeColor: "#000000",
    strokeWidth: 0,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 3,
    shadowOffsetX: 1,
    shadowOffsetY: 1,
    bgStyle: "none",
    bgColor: "#000000",
    bgOpacity: 0,
    bgPadding: 0,
    bgRadius: 0,
    posX: 50,
    posY: 85,
    entranceAnim: "none",
    exitAnim: "none",
    wordAnim: "none",
  },
  bold: {
    fontFamily: "Kantumruy Pro",
    fontSize: 34,
    fontWeight: "800",
    italic: false,
    uppercase: false,
    letterSpacing: 0.5,
    lineHeight: 1.3,
    align: "center",
    textColor: "#38bdf8",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 5,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 8,
    shadowOffsetX: 3,
    shadowOffsetY: 3,
    bgStyle: "none",
    bgColor: "#000000",
    bgOpacity: 0,
    bgPadding: 6,
    bgRadius: 6,
    posX: 50,
    posY: 85,
    entranceAnim: "pop",
    exitAnim: "none",
    wordAnim: "none",
  },
  khmer_clean: {
    fontFamily: "Noto Sans Khmer",
    fontSize: 28,
    fontWeight: "600",
    italic: false,
    uppercase: false,
    letterSpacing: 0,
    lineHeight: 1.45,
    align: "center",
    textColor: "#ffffff",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 2.5,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 4,
    shadowOffsetX: 1,
    shadowOffsetY: 2,
    bgStyle: "semi",
    bgColor: "#09090b",
    bgOpacity: 65,
    bgPadding: 8,
    bgRadius: 8,
    posX: 50,
    posY: 85,
    entranceAnim: "none",
    exitAnim: "none",
    wordAnim: "none",
  },
  khmer_social: {
    fontFamily: "Kantumruy Pro",
    fontSize: 32,
    fontWeight: "800",
    italic: false,
    uppercase: false,
    letterSpacing: 0.5,
    lineHeight: 1.35,
    align: "center",
    textColor: "#f59e0b",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 4,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 6,
    shadowOffsetX: 2,
    shadowOffsetY: 2,
    bgStyle: "rounded",
    bgColor: "#18181b",
    bgOpacity: 90,
    bgPadding: 12,
    bgRadius: 18,
    posX: 50,
    posY: 80,
    entranceAnim: "scale",
    exitAnim: "fadeOut",
    wordAnim: "highlightCurrent",
    karaokeColor: "#fbbf24",
  },
  karaoke: {
    fontFamily: "Kantumruy Pro",
    fontSize: 32,
    fontWeight: "700",
    italic: false,
    uppercase: false,
    letterSpacing: 0.5,
    lineHeight: 1.4,
    align: "center",
    textColor: "#ffffff",
    textOpacity: 100,
    strokeEnabled: true,
    strokeColor: "#000000",
    strokeWidth: 3.5,
    shadowEnabled: true,
    shadowColor: "#000000",
    shadowBlur: 4,
    shadowOffsetX: 2,
    shadowOffsetY: 2,
    bgStyle: "semi",
    bgColor: "#0f172a",
    bgOpacity: 75,
    bgPadding: 10,
    bgRadius: 12,
    posX: 50,
    posY: 85,
    entranceAnim: "fadeIn",
    exitAnim: "none",
    wordAnim: "karaoke",
    karaokeColor: "#facc15",
    karaokeSpeed: 1.0,
  },
};

const SUBTITLE_POSITIONS = {
  "top-left": { x: 20, y: 15, align: "left" },
  "top-center": { x: 50, y: 15, align: "center" },
  "top-right": { x: 80, y: 15, align: "right" },
  "mid-left": { x: 20, y: 50, align: "left" },
  center: { x: 50, y: 50, align: "center" },
  "mid-right": { x: 80, y: 50, align: "right" },
  "bottom-left": { x: 20, y: 85, align: "left" },
  "bottom-center": { x: 50, y: 85, align: "center" },
  "bottom-right": { x: 80, y: 85, align: "right" },
};

function hexToRgba(hex, opacityPct) {
  if (!hex) return "rgba(0,0,0,0.6)";
  let c = hex.replace("#", "");
  if (c.length === 3) c = c.split("").map((x) => x + x).join("");
  const num = parseInt(c, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  const a = Math.max(0, Math.min(1, (opacityPct ?? 100) / 100));
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

function tokenizeWords(text) {
  if (!text) return [];
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (words.length <= 1 && text.length > 8) {
    const chunks = [];
    for (let i = 0; i < text.length; i += 4) {
      chunks.push(text.slice(i, i + 4));
    }
    return chunks;
  }
  return words;
}

// Subtitle History (Undo / Redo)
function pushSubtitleHistory(actionName) {
  appState.subtitleHistory.push({
    subtitles: JSON.parse(JSON.stringify(appState.subtitles)),
    style: JSON.parse(JSON.stringify(appState.subtitleStyle)),
    action: actionName || "Edit",
  });
  if (appState.subtitleHistory.length > 40) {
    appState.subtitleHistory.shift();
  }
  appState.subtitleRedoStack = [];
}

function undoSubtitles() {
  if (!appState.subtitleHistory || appState.subtitleHistory.length === 0) {
    showToast("Nothing to undo in subtitles");
    return;
  }
  const currentSnapshot = {
    subtitles: JSON.parse(JSON.stringify(appState.subtitles)),
    style: JSON.parse(JSON.stringify(appState.subtitleStyle)),
  };
  appState.subtitleRedoStack.push(currentSnapshot);

  const prev = appState.subtitleHistory.pop();
  appState.subtitles = prev.subtitles;
  appState.subtitleStyle = prev.style;

  syncSubtitleControlsFromState();
  renderSubtitlesTable();
  renderTimelineBlocks();
  updateStatusMetrics();
  updateVideoSubtitleOverlay(appState.currentTime);
  showToast(`Undo: ${prev.action || "change"}`);
}

function redoSubtitles() {
  if (!appState.subtitleRedoStack || appState.subtitleRedoStack.length === 0) {
    showToast("Nothing to redo in subtitles");
    return;
  }
  const nextSnapshot = appState.subtitleRedoStack.pop();
  appState.subtitleHistory.push({
    subtitles: JSON.parse(JSON.stringify(appState.subtitles)),
    style: JSON.parse(JSON.stringify(appState.subtitleStyle)),
    action: "Redo",
  });

  appState.subtitles = nextSnapshot.subtitles;
  appState.subtitleStyle = nextSnapshot.style;

  syncSubtitleControlsFromState();
  renderSubtitlesTable();
  renderTimelineBlocks();
  updateStatusMetrics();
  updateVideoSubtitleOverlay(appState.currentTime);
  showToast("Redo applied");
}

// Sync Quick Subtitle Editor Box with active segment

// Switch between Voice Dubbing, Subtitle Studio, and Story Recap Tabs
function switchStudioTab(tab) {
  appState.activeStudioTab = tab;

  // Toggle Tab Nav Buttons
  if (ui.tabTriggerVoice) ui.tabTriggerVoice.classList.toggle("active", tab === "voice");
  if (ui.tabTriggerSubtitles) ui.tabTriggerSubtitles.classList.toggle("active", tab === "subtitles");
  if (ui.tabTriggerRecap) ui.tabTriggerRecap.classList.toggle("active", tab === "recap");

  // Toggle Side Toolbar Buttons
  if (ui.btnSideToolbarSubtitles) ui.btnSideToolbarSubtitles.classList.toggle("active-tool", tab === "subtitles");
  if (ui.btnSideToolbarRecap) ui.btnSideToolbarRecap.classList.toggle("active-tool", tab === "recap");
  if (ui.btnSideToolbarBlur) ui.btnSideToolbarBlur.classList.toggle("active-tool", Boolean(appState.blurStudio?.enabled && tab === "voice"));

  // Auto-apply and deselect blur when switching AWAY from voice tab
  if (tab !== "voice" && appState.blurStudio && appState.blurStudio.activeBlurId) {
    deselectBlurObject(true);
  } else if (tab === "voice" && appState.blurStudio && appState.blurStudio.enabled) {
    if (!appState.blurStudio.activeBlurId && appState.blurStudio.objects?.length > 0) {
      appState.blurStudio.activeBlurId = appState.blurStudio.objects[0].id;
    }
    if (ui.blurSubpanel) {
      ui.blurSubpanel.classList.remove("hidden");
      ui.blurSubpanel.style.display = "flex";
    }
    const active = getActiveBlurObject();
    if (active) syncBlurControlsFromObject(active);
    renderBlurLayersList();
  }

  // Toggle Subpanels
  if (ui.subpanelVoiceSettings) {
    ui.subpanelVoiceSettings.classList.toggle("hidden", tab !== "voice");
    ui.subpanelVoiceSettings.style.display = tab === "voice" ? "flex" : "none";
  }
  if (ui.subpanelSubtitleStudio) {
    ui.subpanelSubtitleStudio.classList.toggle("hidden", tab !== "subtitles");
    ui.subpanelSubtitleStudio.style.display = tab === "subtitles" ? "flex" : "none";
  }
  if (ui.subpanelRecapStudio) {
    ui.subpanelRecapStudio.classList.toggle("hidden", tab !== "recap");
    ui.subpanelRecapStudio.style.display = tab === "recap" ? "flex" : "none";
  }

  if (tab === "subtitles") {
    openSubtitleStudioDialog();
  }
  if (tab === "recap") {
    openRecapStudioDialog();
  }

  // Update Headings
  const mainHeading = document.getElementById("panelMainHeading");
  const subHeading = document.getElementById("panelSubHeading");
  if (mainHeading && subHeading) {
    if (tab === "recap") {
      mainHeading.textContent = "Movie Recap Studio (សម្រាយរឿង)";
      subHeading.textContent = "Auto-generate viral third-person movie recap narration with AI & BGM ducking";
    } else {
      mainHeading.textContent = "Voice Dubbing Studio";
      subHeading.textContent = "Configure neural voice dubbing, speaker assignment & video translation";
    }
  }

  if (tab === "subtitles") {
    syncSubtitleControlsFromState();
    const activeSub = appState.subtitles.find((s) => s.id === appState.activeSubtitleId) || appState.subtitles[0];
    if (activeSub) syncSubtitleQuickEditor(activeSub);
  }

  updateVideoSubtitleOverlay(appState.currentTime);
}

// Sync Style Controls from appState.subtitleStyle
function syncSubtitleControlsFromState() {
  const st = appState.subtitleStyle;
  if (!st) return;

  if (ui.subFontFamily) ui.subFontFamily.value = st.fontFamily;
  if (ui.rangeSubFontSize) ui.rangeSubFontSize.value = st.fontSize;
  if (ui.valSubFontSize) ui.valSubFontSize.textContent = `${st.fontSize}px`;
  if (ui.selectSubFontWeight) ui.selectSubFontWeight.value = st.fontWeight;

  if (ui.subAlignGroup) {
    ui.subAlignGroup.querySelectorAll(".btn-seg-item").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.align === st.align);
    });
  }

  if (ui.btnSubItalic) ui.btnSubItalic.classList.toggle("active", Boolean(st.italic));
  if (ui.btnSubUppercase) ui.btnSubUppercase.classList.toggle("active", Boolean(st.uppercase));
  if (ui.rangeSubLetterSpacing) ui.rangeSubLetterSpacing.value = st.letterSpacing;
  if (ui.valSubLetterSpacing) ui.valSubLetterSpacing.textContent = `${st.letterSpacing}px`;
  if (ui.rangeSubLineHeight) ui.rangeSubLineHeight.value = st.lineHeight;
  if (ui.valSubLineHeight) ui.valSubLineHeight.textContent = st.lineHeight;

  if (ui.inputSubTextColor) ui.inputSubTextColor.value = st.textColor;
  if (ui.hexSubTextColor) ui.hexSubTextColor.value = st.textColor;
  if (ui.rangeSubTextOpacity) ui.rangeSubTextOpacity.value = st.textOpacity ?? 100;
  if (ui.valSubTextOpacity) ui.valSubTextOpacity.textContent = `${st.textOpacity ?? 100}%`;

  if (ui.chkSubStroke) ui.chkSubStroke.checked = st.strokeEnabled;
  if (ui.subStrokeControls) ui.subStrokeControls.classList.toggle("hidden", !st.strokeEnabled);
  if (ui.inputSubStrokeColor) ui.inputSubStrokeColor.value = st.strokeColor;
  if (ui.hexSubStrokeColor) ui.hexSubStrokeColor.value = st.strokeColor;
  if (ui.rangeSubStrokeWidth) ui.rangeSubStrokeWidth.value = st.strokeWidth;
  if (ui.valSubStrokeWidth) ui.valSubStrokeWidth.textContent = `${st.strokeWidth}px`;

  if (ui.chkSubShadow) ui.chkSubShadow.checked = st.shadowEnabled;
  if (ui.subShadowControls) ui.subShadowControls.classList.toggle("hidden", !st.shadowEnabled);
  if (ui.inputSubShadowColor) ui.inputSubShadowColor.value = st.shadowColor;
  if (ui.hexSubShadowColor) ui.hexSubShadowColor.value = st.shadowColor;
  if (ui.rangeSubShadowBlur) ui.rangeSubShadowBlur.value = st.shadowBlur;
  if (ui.valSubShadowBlur) ui.valSubShadowBlur.textContent = `${st.shadowBlur}px`;
  if (ui.rangeSubShadowOffsetX) ui.rangeSubShadowOffsetX.value = st.shadowOffsetX;
  if (ui.valSubShadowOffsetX) ui.valSubShadowOffsetX.textContent = `${st.shadowOffsetX}px`;
  if (ui.rangeSubShadowOffsetY) ui.rangeSubShadowOffsetY.value = st.shadowOffsetY;
  if (ui.valSubShadowOffsetY) ui.valSubShadowOffsetY.textContent = `${st.shadowOffsetY}px`;

  if (ui.selectSubBgStyle) ui.selectSubBgStyle.value = st.bgStyle;
  if (ui.subBgControlsGroup) ui.subBgControlsGroup.classList.toggle("hidden", st.bgStyle === "none");
  if (ui.inputSubBgColor) ui.inputSubBgColor.value = st.bgColor;
  if (ui.hexSubBgColor) ui.hexSubBgColor.value = st.bgColor;
  if (ui.rangeSubBgOpacity) ui.rangeSubBgOpacity.value = st.bgOpacity;
  if (ui.valSubBgOpacity) ui.valSubBgOpacity.textContent = `${st.bgOpacity}%`;
  if (ui.rangeSubBgPadding) ui.rangeSubBgPadding.value = st.bgPadding;
  if (ui.valSubBgPadding) ui.valSubBgPadding.textContent = `${st.bgPadding}px`;
  if (ui.rangeSubBgRadius) ui.rangeSubBgRadius.value = st.bgRadius;
  if (ui.valSubBgRadius) ui.valSubBgRadius.textContent = `${st.bgRadius}px`;
  if (ui.rangeSubBgBlur) ui.rangeSubBgBlur.value = st.bgBlur ?? 12;
  if (ui.valSubBgBlur) ui.valSubBgBlur.textContent = `${st.bgBlur ?? 12}px`;

  if (ui.rangeSubPosX) ui.rangeSubPosX.value = st.posX;
  if (ui.valSubPosX) ui.valSubPosX.textContent = `${st.posX}%`;
  if (ui.rangeSubPosY) ui.rangeSubPosY.value = st.posY;
  if (ui.valSubPosY) ui.valSubPosY.textContent = `${st.posY}%`;

  if (ui.subPositionGrid) {
    ui.subPositionGrid.querySelectorAll(".btn-grid-pos").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.pos === st.positionPreset);
    });
  }

  if (ui.chkSubSafeArea) ui.chkSubSafeArea.checked = Boolean(st.safeAreaEnabled);
  if (ui.subtitleSafeAreaOverlay) {
    ui.subtitleSafeAreaOverlay.style.display = st.safeAreaEnabled ? "block" : "none";
  }

  if (ui.selectSubEntrance) ui.selectSubEntrance.value = st.entranceAnim || "none";
  if (ui.selectSubExit) ui.selectSubExit.value = st.exitAnim || "none";
  if (ui.selectSubWordAnim) ui.selectSubWordAnim.value = st.wordAnim || "none";
  if (ui.inputKaraokeColor) ui.inputKaraokeColor.value = st.karaokeColor || "#facc15";
  if (ui.hexKaraokeColor) ui.hexKaraokeColor.value = st.karaokeColor || "#facc15";
  if (ui.rangeKaraokeSpeed) ui.rangeKaraokeSpeed.value = st.karaokeSpeed || 1.0;
  if (ui.valKaraokeSpeed) ui.valKaraokeSpeed.textContent = `${st.karaokeSpeed || 1.0}x`;
  if (ui.selectSubLangMode) ui.selectSubLangMode.value = st.langMode || "khmer";
}

// Apply Preset
function applySubtitlePreset(presetKey) {
  const p = SUBTITLE_PRESETS[presetKey];
  if (!p) return;
  pushSubtitleHistory(`Preset: ${presetKey}`);
  appState.subtitleStyle = {
    ...appState.subtitleStyle,
    ...p,
    preset: presetKey,
  };
  if (ui.subPresetChips) {
    ui.subPresetChips.querySelectorAll(".preset-chip").forEach((c) => {
      c.classList.toggle("active", c.dataset.subpreset === presetKey);
    });
  }
  syncSubtitleControlsFromState();
  updateVideoSubtitleOverlay(appState.currentTime);
  showToast(`Applied preset: ${presetKey.toUpperCase()}`);
}

// Apply Position Preset
function setSubtitlePosition(posKey) {
  const p = SUBTITLE_POSITIONS[posKey];
  if (!p) return;
  pushSubtitleHistory(`Position: ${posKey}`);
  appState.subtitleStyle.posX = p.x;
  appState.subtitleStyle.posY = p.y;
  appState.subtitleStyle.align = p.align;
  appState.subtitleStyle.positionPreset = posKey;
  syncSubtitleControlsFromState();
  updateVideoSubtitleOverlay(appState.currentTime);
}

// Sync Quick Editor in Studio Sidebar
function syncSubtitleQuickEditor(sub) {
  if (!sub) {
    sub = appState.subtitles.find((s) => s.id === appState.activeSubtitleId) || appState.subtitles[0];
  }
  if (!sub) {
    if (ui.subActiveSegmentBadge) ui.subActiveSegmentBadge.textContent = "No Segments";
    if (ui.subActiveCounter) ui.subActiveCounter.textContent = "0 of 0";
    if (ui.subTextKhmerInput) ui.subTextKhmerInput.value = "";
    if (ui.subTextOrigInput) ui.subTextOrigInput.value = "";
    return;
  }

  const idx = appState.subtitles.findIndex((s) => s.id === sub.id);
  const total = appState.subtitles.length;

  if (ui.subActiveSegmentBadge) {
    ui.subActiveSegmentBadge.textContent = `#${idx + 1} (${formatTimecodePrecise(sub.start)} - ${formatTimecodePrecise(sub.end)})`;
  }
  if (ui.subActiveCounter) {
    ui.subActiveCounter.textContent = `${idx + 1} of ${total}`;
  }
  if (ui.subTextKhmerInput && document.activeElement !== ui.subTextKhmerInput) {
    ui.subTextKhmerInput.value = sub.khmer_text || "";
  }
  if (ui.subTextOrigInput && document.activeElement !== ui.subTextOrigInput) {
    ui.subTextOrigInput.value = sub.text || "";
  }
  if (ui.selectSubSpeaker) {
    ui.selectSubSpeaker.value = sub.speaker || "Speaker 1";
  }
  if (ui.selectSubLangMode) {
    ui.selectSubLangMode.value = appState.subtitleStyle.langMode || "khmer";
  }
}

// Direct Interactive Manipulation on Video Preview
function initSubtitleDirectManipulation() {
  if (!ui.subtitleBoxBounds || !ui.playerAspectWrapper) return;

  let dragMode = null; // 'box', 'rotate', 'nw', 'ne', 'se', 'sw', 'e', 'w'
  let startX = 0;
  let startY = 0;
  let startPosX = 50;
  let startPosY = 85;
  let startFontSize = 28;
  let startRotation = 0;
  let boxCenter = { x: 0, y: 0 };

  function onPointerDown(e) {
    if (e.button !== undefined && e.button !== 0) return;
    if (appState.subtitles.length === 0) return;

    // Switch to Subtitles tab on click if not active
    if (appState.activeStudioTab !== "subtitles") {
      switchStudioTab("subtitles");
    }

    const rotHandle = e.target.closest("#subRotateHandle");
    const resHandle = e.target.closest(".sub-resizer");

    if (rotHandle) {
      dragMode = "rotate";
      const rect = ui.subtitleBoxBounds.getBoundingClientRect();
      boxCenter = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
      startRotation = appState.subtitleStyle.rotation || 0;
    } else if (resHandle && resHandle.dataset.handle) {
      dragMode = resHandle.dataset.handle;
      startFontSize = appState.subtitleStyle.fontSize || 28;
    } else {
      dragMode = "box";
    }

    startX = e.clientX;
    startY = e.clientY;
    startPosX = appState.subtitleStyle.posX ?? 50;
    startPosY = appState.subtitleStyle.posY ?? 85;

    e.stopPropagation();
    e.preventDefault();

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
  }

  function onPointerMove(e) {
    if (!dragMode) return;
    const vRect = (typeof getVideoRenderedRect === "function" && getVideoRenderedRect()) || ui.playerAspectWrapper.getBoundingClientRect();
    if (!vRect.width || !vRect.height) return;

    if (dragMode === "rotate") {
      const angleRad = Math.atan2(e.clientY - boxCenter.y, e.clientX - boxCenter.x);
      let deg = Math.round((angleRad * 180) / Math.PI) + 90;
      if (deg > 180) deg -= 360;
      if (deg < -180) deg += 360;
      appState.subtitleStyle.rotation = deg;
    } else if (dragMode === "box") {
      const dxPct = ((e.clientX - startX) / vRect.width) * 100;
      const dyPct = ((e.clientY - startY) / vRect.height) * 100;
      const newX = Math.round(Math.max(5, Math.min(95, startPosX + dxPct)));
      const newY = Math.round(Math.max(5, Math.min(95, startPosY + dyPct)));
      appState.subtitleStyle.posX = newX;
      appState.subtitleStyle.posY = newY;
    } else {
      // Resize handles scale font size proportionally
      const dy = e.clientY - startY;
      const delta = dragMode.includes("s") ? dy : -dy;
      const newSize = Math.max(14, Math.min(72, Math.round(startFontSize + delta * 0.4)));
      appState.subtitleStyle.fontSize = newSize;
    }

    syncSubtitleControlsFromState();
    updateVideoSubtitleOverlay(appState.currentTime);
  }

  function onPointerUp() {
    if (dragMode) {
      pushSubtitleHistory(`Transform ${dragMode}`);
      dragMode = null;
    }
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    window.removeEventListener("pointercancel", onPointerUp);
  }

  ui.subtitleBoxBounds.addEventListener("pointerdown", onPointerDown);

  // Double Click for Live Inline Text Editing
  ui.subtitleBoxBounds.addEventListener("dblclick", (e) => {
    e.stopPropagation();
    const sub = appState.subtitles.find((s) => s.id === appState.activeSubtitleId) ||
      appState.subtitles.find((s) => appState.currentTime >= s.start && appState.currentTime <= s.end);
    if (!sub) return;

    if (!ui.inlineSubtitleEditor) return;
    const isKhmer = appState.subtitleStyle.langMode === "khmer";
    ui.inlineSubtitleEditor.value = isKhmer ? (sub.khmer_text || sub.text || "") : (sub.text || sub.khmer_text || "");
    ui.inlineSubtitleEditor.classList.remove("hidden");
    ui.inlineSubtitleEditor.style.display = "block";
    ui.inlineSubtitleEditor.focus();
    ui.inlineSubtitleEditor.select();

    function onEditorKeyDown(ev) {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        commitInlineEdit();
      } else if (ev.key === "Escape") {
        ev.preventDefault();
        cancelInlineEdit();
      }
    }

    function commitInlineEdit() {
      const val = ui.inlineSubtitleEditor.value.trim();
      pushSubtitleHistory("Inline text edit");
      if (isKhmer) {
        sub.khmer_text = val;
      } else {
        sub.text = val;
      }
      ui.inlineSubtitleEditor.classList.add("hidden");
      ui.inlineSubtitleEditor.style.display = "none";
      ui.inlineSubtitleEditor.removeEventListener("keydown", onEditorKeyDown);
      ui.inlineSubtitleEditor.removeEventListener("blur", commitInlineEdit);
      renderSubtitlesTable();
      renderTimelineBlocks();
      updateStatusMetrics();
      syncSubtitleQuickEditor(sub);
      updateVideoSubtitleOverlay(appState.currentTime);
      showToast("Subtitle text updated!");
    }

    function cancelInlineEdit() {
      ui.inlineSubtitleEditor.classList.add("hidden");
      ui.inlineSubtitleEditor.style.display = "none";
      ui.inlineSubtitleEditor.removeEventListener("keydown", onEditorKeyDown);
      ui.inlineSubtitleEditor.removeEventListener("blur", commitInlineEdit);
    }

    ui.inlineSubtitleEditor.addEventListener("keydown", onEditorKeyDown);
    ui.inlineSubtitleEditor.addEventListener("blur", commitInlineEdit);
  });
}

// Bind Subtitle Studio Controls & Export Events
function bindSubtitleStudioEvents() {
  // Tabs Switcher
  if (ui.tabTriggerVoice) {
    ui.tabTriggerVoice.addEventListener("click", () => switchStudioTab("voice"));
  }
  if (ui.tabTriggerSubtitles) {
    ui.tabTriggerSubtitles.addEventListener("click", () => switchStudioTab("subtitles"));
  }
  if (ui.btnSideToolbarSubtitles) {
    ui.btnSideToolbarSubtitles.addEventListener("click", () => switchStudioTab("subtitles"));
  }

  // Quick Editor Navigation Buttons
  if (ui.btnSubNavPrev) {
    ui.btnSubNavPrev.addEventListener("click", () => {
      const idx = appState.subtitles.findIndex((s) => s.id === appState.activeSubtitleId);
      if (idx > 0) {
        selectAndSeekSubtitle(appState.subtitles[idx - 1]);
      }
    });
  }
  if (ui.btnSubNavNext) {
    ui.btnSubNavNext.addEventListener("click", () => {
      const idx = appState.subtitles.findIndex((s) => s.id === appState.activeSubtitleId);
      if (idx !== -1 && idx < appState.subtitles.length - 1) {
        selectAndSeekSubtitle(appState.subtitles[idx + 1]);
      }
    });
  }
  if (ui.btnSubAddCurrent) {
    ui.btnSubAddCurrent.addEventListener("click", () => addNewSubtitleSegment());
  }

  // Quick Editor Text Inputs
  if (ui.subTextKhmerInput) {
    ui.subTextKhmerInput.addEventListener("input", (e) => {
      const sub = appState.subtitles.find((s) => s.id === appState.activeSubtitleId);
      if (sub) {
        sub.khmer_text = e.target.value;
        updateVideoSubtitleOverlay(appState.currentTime);
        const row = document.getElementById(`sub-row-${sub.id}`);
        if (row) {
          const khmerCell = row.querySelector(".col-khmer textarea");
          if (khmerCell && document.activeElement !== khmerCell) khmerCell.value = sub.khmer_text;
        }
      }
    });
    ui.subTextKhmerInput.addEventListener("blur", () => {
      pushSubtitlesHistory();
      renderSubtitlesTable();
    });
  }
  if (ui.subTextOrigInput) {
    ui.subTextOrigInput.addEventListener("input", (e) => {
      const sub = appState.subtitles.find((s) => s.id === appState.activeSubtitleId);
      if (sub) {
        sub.text = e.target.value;
        updateVideoSubtitleOverlay(appState.currentTime);
        const row = document.getElementById(`sub-row-${sub.id}`);
        if (row) {
          const origCell = row.querySelector(".col-orig textarea");
          if (origCell && document.activeElement !== origCell) origCell.value = sub.text;
        }
      }
    });
    ui.subTextOrigInput.addEventListener("blur", () => {
      pushSubtitlesHistory();
      renderSubtitlesTable();
    });
  }
  if (ui.selectSubSpeaker) {
    ui.selectSubSpeaker.addEventListener("change", (e) => {
      const sub = appState.subtitles.find((s) => s.id === appState.activeSubtitleId);
      if (sub) {
        sub.speaker = e.target.value;
        renderSubtitlesTable();
        updateVideoSubtitleOverlay(appState.currentTime);
      }
    });
  }
  if (ui.selectSubLangMode) {
    ui.selectSubLangMode.addEventListener("change", (e) => {
      appState.subtitleStyle.langMode = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }

  // Presets Chips
  if (ui.subPresetChips) {
    ui.subPresetChips.querySelectorAll(".preset-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        applySubtitlePreset(chip.dataset.subpreset);
      });
    });
  }

  // Typography Controls
  if (ui.subFontFamily) {
    ui.subFontFamily.addEventListener("change", (e) => {
      pushSubtitleHistory("Font family");
      appState.subtitleStyle.fontFamily = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubFontSize) {
    ui.rangeSubFontSize.addEventListener("input", (e) => {
      appState.subtitleStyle.fontSize = parseInt(e.target.value, 10);
      if (ui.valSubFontSize) ui.valSubFontSize.textContent = `${e.target.value}px`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
    ui.rangeSubFontSize.addEventListener("change", () => pushSubtitleHistory("Font size"));
  }
  if (ui.selectSubFontWeight) {
    ui.selectSubFontWeight.addEventListener("change", (e) => {
      pushSubtitleHistory("Font weight");
      appState.subtitleStyle.fontWeight = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.subAlignGroup) {
    ui.subAlignGroup.querySelectorAll(".btn-seg-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        pushSubtitleHistory("Alignment");
        appState.subtitleStyle.align = btn.dataset.align;
        syncSubtitleControlsFromState();
        updateVideoSubtitleOverlay(appState.currentTime);
      });
    });
  }
  if (ui.btnSubItalic) {
    ui.btnSubItalic.addEventListener("click", () => {
      pushSubtitleHistory("Italic");
      appState.subtitleStyle.italic = !appState.subtitleStyle.italic;
      syncSubtitleControlsFromState();
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.btnSubUppercase) {
    ui.btnSubUppercase.addEventListener("click", () => {
      pushSubtitleHistory("Uppercase");
      appState.subtitleStyle.uppercase = !appState.subtitleStyle.uppercase;
      syncSubtitleControlsFromState();
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubLetterSpacing) {
    ui.rangeSubLetterSpacing.addEventListener("input", (e) => {
      appState.subtitleStyle.letterSpacing = parseFloat(e.target.value);
      if (ui.valSubLetterSpacing) ui.valSubLetterSpacing.textContent = `${e.target.value}px`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubLineHeight) {
    ui.rangeSubLineHeight.addEventListener("input", (e) => {
      appState.subtitleStyle.lineHeight = parseFloat(e.target.value);
      if (ui.valSubLineHeight) ui.valSubLineHeight.textContent = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }

  // Text Color & Opacity
  if (ui.inputSubTextColor) {
    ui.inputSubTextColor.addEventListener("input", (e) => {
      appState.subtitleStyle.textColor = e.target.value;
      if (ui.hexSubTextColor) ui.hexSubTextColor.value = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.hexSubTextColor) {
    ui.hexSubTextColor.addEventListener("change", (e) => {
      appState.subtitleStyle.textColor = e.target.value;
      if (ui.inputSubTextColor) ui.inputSubTextColor.value = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubTextOpacity) {
    ui.rangeSubTextOpacity.addEventListener("input", (e) => {
      appState.subtitleStyle.textOpacity = parseInt(e.target.value, 10);
      if (ui.valSubTextOpacity) ui.valSubTextOpacity.textContent = `${e.target.value}%`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }

  // Stroke / Outline
  if (ui.chkSubStroke) {
    ui.chkSubStroke.addEventListener("change", (e) => {
      pushSubtitleHistory("Stroke toggle");
      appState.subtitleStyle.strokeEnabled = e.target.checked;
      syncSubtitleControlsFromState();
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.inputSubStrokeColor) {
    ui.inputSubStrokeColor.addEventListener("input", (e) => {
      appState.subtitleStyle.strokeColor = e.target.value;
      if (ui.hexSubStrokeColor) ui.hexSubStrokeColor.value = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubStrokeWidth) {
    ui.rangeSubStrokeWidth.addEventListener("input", (e) => {
      appState.subtitleStyle.strokeWidth = parseFloat(e.target.value);
      if (ui.valSubStrokeWidth) ui.valSubStrokeWidth.textContent = `${e.target.value}px`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }

  // Shadow
  if (ui.chkSubShadow) {
    ui.chkSubShadow.addEventListener("change", (e) => {
      pushSubtitleHistory("Shadow toggle");
      appState.subtitleStyle.shadowEnabled = e.target.checked;
      syncSubtitleControlsFromState();
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.inputSubShadowColor) {
    ui.inputSubShadowColor.addEventListener("input", (e) => {
      appState.subtitleStyle.shadowColor = e.target.value;
      if (ui.hexSubShadowColor) ui.hexSubShadowColor.value = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubShadowBlur) {
    ui.rangeSubShadowBlur.addEventListener("input", (e) => {
      appState.subtitleStyle.shadowBlur = parseInt(e.target.value, 10);
      if (ui.valSubShadowBlur) ui.valSubShadowBlur.textContent = `${e.target.value}px`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubShadowOffsetX) {
    ui.rangeSubShadowOffsetX.addEventListener("input", (e) => {
      appState.subtitleStyle.shadowOffsetX = parseInt(e.target.value, 10);
      if (ui.valSubShadowOffsetX) ui.valSubShadowOffsetX.textContent = `${e.target.value}px`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubShadowOffsetY) {
    ui.rangeSubShadowOffsetY.addEventListener("input", (e) => {
      appState.subtitleStyle.shadowOffsetY = parseInt(e.target.value, 10);
      if (ui.valSubShadowOffsetY) ui.valSubShadowOffsetY.textContent = `${e.target.value}px`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }

  // Background Box
  if (ui.selectSubBgStyle) {
    ui.selectSubBgStyle.addEventListener("change", (e) => {
      pushSubtitleHistory("Background style");
      appState.subtitleStyle.bgStyle = e.target.value;
      syncSubtitleControlsFromState();
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.inputSubBgColor) {
    ui.inputSubBgColor.addEventListener("input", (e) => {
      appState.subtitleStyle.bgColor = e.target.value;
      if (ui.hexSubBgColor) ui.hexSubBgColor.value = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubBgOpacity) {
    ui.rangeSubBgOpacity.addEventListener("input", (e) => {
      appState.subtitleStyle.bgOpacity = parseInt(e.target.value, 10);
      if (ui.valSubBgOpacity) ui.valSubBgOpacity.textContent = `${e.target.value}%`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubBgPadding) {
    ui.rangeSubBgPadding.addEventListener("input", (e) => {
      appState.subtitleStyle.bgPadding = parseInt(e.target.value, 10);
      if (ui.valSubBgPadding) ui.valSubBgPadding.textContent = `${e.target.value}px`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubBgRadius) {
    ui.rangeSubBgRadius.addEventListener("input", (e) => {
      appState.subtitleStyle.bgRadius = parseInt(e.target.value, 10);
      if (ui.valSubBgRadius) ui.valSubBgRadius.textContent = `${e.target.value}px`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubBgBlur) {
    ui.rangeSubBgBlur.addEventListener("input", (e) => {
      appState.subtitleStyle.bgBlur = parseInt(e.target.value, 10);
      if (ui.valSubBgBlur) ui.valSubBgBlur.textContent = `${e.target.value}px`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }

  // Position Matrix & Sliders
  if (ui.subPositionGrid) {
    ui.subPositionGrid.querySelectorAll(".btn-grid-pos").forEach((btn) => {
      btn.addEventListener("click", () => {
        setSubtitlePosition(btn.dataset.pos);
      });
    });
  }
  if (ui.rangeSubPosX) {
    ui.rangeSubPosX.addEventListener("input", (e) => {
      appState.subtitleStyle.posX = parseInt(e.target.value, 10);
      if (ui.valSubPosX) ui.valSubPosX.textContent = `${e.target.value}%`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeSubPosY) {
    ui.rangeSubPosY.addEventListener("input", (e) => {
      appState.subtitleStyle.posY = parseInt(e.target.value, 10);
      if (ui.valSubPosY) ui.valSubPosY.textContent = `${e.target.value}%`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.chkSubSafeArea) {
    ui.chkSubSafeArea.addEventListener("change", (e) => {
      appState.subtitleStyle.safeAreaEnabled = e.target.checked;
      syncSubtitleControlsFromState();
      showToast(e.target.checked ? "Safe Area Guides Visible" : "Safe Area Guides Hidden");
    });
  }

  // Animation & Karaoke
  if (ui.selectSubEntrance) {
    ui.selectSubEntrance.addEventListener("change", (e) => {
      pushSubtitleHistory("Entrance animation");
      appState.subtitleStyle.entranceAnim = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.selectSubExit) {
    ui.selectSubExit.addEventListener("change", (e) => {
      pushSubtitleHistory("Exit animation");
      appState.subtitleStyle.exitAnim = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.selectSubWordAnim) {
    ui.selectSubWordAnim.addEventListener("change", (e) => {
      pushSubtitleHistory("Word animation mode");
      appState.subtitleStyle.wordAnim = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.inputKaraokeColor) {
    ui.inputKaraokeColor.addEventListener("input", (e) => {
      appState.subtitleStyle.karaokeColor = e.target.value;
      if (ui.hexKaraokeColor) ui.hexKaraokeColor.value = e.target.value;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }
  if (ui.rangeKaraokeSpeed) {
    ui.rangeKaraokeSpeed.addEventListener("input", (e) => {
      appState.subtitleStyle.karaokeSpeed = parseFloat(e.target.value);
      if (ui.valKaraokeSpeed) ui.valKaraokeSpeed.textContent = `${e.target.value}x`;
      updateVideoSubtitleOverlay(appState.currentTime);
    });
  }

  // Subtitle Tracks List Toggles
  if (ui.subTracksList) {
    ui.subTracksList.querySelectorAll(".sub-track-item").forEach((item) => {
      item.addEventListener("click", () => {
        ui.subTracksList.querySelectorAll(".sub-track-item").forEach((it) => it.classList.remove("active"));
        item.classList.add("active");
        const trackId = item.dataset.trackId;
        if (trackId === "track_khmer") {
          appState.subtitleStyle.langMode = "khmer";
        } else if (trackId === "track_orig") {
          appState.subtitleStyle.langMode = "orig";
        }
        syncSubtitleControlsFromState();
        updateVideoSubtitleOverlay(appState.currentTime);
      });
    });
  }

  // Quick Export Buttons (/api/subtitles/export)
  async function triggerSubtitleExport(format) {
    if (appState.subtitles.length === 0) {
      showToast("No subtitles to export. Add or generate subtitles first.");
      return;
    }
    showToast(`Generating ${format.toUpperCase()} subtitle export...`);
    try {
      const res = await fetch("/api/subtitles/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: appState.sessionId,
          segments: appState.subtitles,
          format: format,
          style: appState.subtitleStyle,
          language_mode: appState.subtitleStyle.langMode || "khmer",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Subtitle export failed");
      }

      const data = await res.json();
      if (data.download_url) {
        const a = document.createElement("a");
        a.href = data.download_url;
        a.download = data.filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        showToast(`Downloaded ${data.filename}!`);
      }
    } catch (err) {
      console.error("Subtitle export error:", err);
      showToast(`Export error: ${err.message}`);
    }
  }

  if (ui.btnQuickExportAss) {
    ui.btnQuickExportAss.addEventListener("click", () => triggerSubtitleExport("ass"));
  }
  if (ui.btnQuickExportSrt) {
    ui.btnQuickExportSrt.addEventListener("click", () => triggerSubtitleExport("srt"));
  }
  if (ui.btnQuickExportVtt) {
    ui.btnQuickExportVtt.addEventListener("click", () => triggerSubtitleExport("vtt"));
  }

  if (ui.chkBurnSubtitlesExport) {
    ui.chkBurnSubtitlesExport.addEventListener("change", () => {
      const active = Boolean(ui.chkBurnSubtitlesExport.checked);
      if (ui.chkExportModalBurnSubs) ui.chkExportModalBurnSubs.checked = active;
      showToast(active ? "🔥 Burn Subtitles into Video: Enabled" : "Burn Subtitles into Video: Disabled");
    });
  }
  if (ui.chkExportModalBurnSubs) {
    ui.chkExportModalBurnSubs.addEventListener("change", () => {
      const active = Boolean(ui.chkExportModalBurnSubs.checked);
      if (ui.chkBurnSubtitlesExport) ui.chkBurnSubtitlesExport.checked = active;
      showToast(active ? "🔥 Burn Subtitles into Video: Enabled" : "Burn Subtitles into Video: Disabled");
    });
  }

  // Global Keyboard Shortcuts (Space, S, Delete, Ctrl+Z, Ctrl+Y, Shift+Left/Right, Enter)
  window.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName) || "";
    const isInput = ["INPUT", "TEXTAREA", "SELECT"].includes(tag);

    // Undo / Redo (Ctrl+Z, Ctrl+Y)
    if ((e.ctrlKey || e.metaKey) && !isInput) {
      if (e.key === "z" || e.key === "Z") {
        if (e.shiftKey) {
          e.preventDefault();
          redoSubtitles();
        } else {
          e.preventDefault();
          undoSubtitles();
        }
        return;
      } else if (e.key === "y" || e.key === "Y") {
        e.preventDefault();
        redoSubtitles();
        return;
      }
    }

    if (isInput) return;

    // S key: Add subtitle at current playhead
    if (e.key === "s" || e.key === "S") {
      e.preventDefault();
      addNewSubtitleSegment();
      return;
    }

    // Delete key: Delete active subtitle
    if (e.key === "Delete" || e.key === "Backspace") {
      if (appState.activeSubtitleId && appState.activeStudioTab === "subtitles") {
        e.preventDefault();
        deleteSelectedSubtitle();
        return;
      }
    }

    // Shift + Left: Previous subtitle
    if (e.shiftKey && e.key === "ArrowLeft") {
      e.preventDefault();
      const idx = appState.subtitles.findIndex((s) => s.id === appState.activeSubtitleId);
      if (idx > 0) selectAndSeekSubtitle(appState.subtitles[idx - 1]);
      return;
    }

    // Shift + Right: Next subtitle
    if (e.shiftKey && e.key === "ArrowRight") {
      e.preventDefault();
      const idx = appState.subtitles.findIndex((s) => s.id === appState.activeSubtitleId);
      if (idx !== -1 && idx < appState.subtitles.length - 1) {
        selectAndSeekSubtitle(appState.subtitles[idx + 1]);
      }
      return;
    }

    // Enter key: Edit active subtitle inline
    if (e.key === "Enter" && appState.activeStudioTab === "subtitles" && ui.subtitleBoxBounds) {
      e.preventDefault();
      ui.subtitleBoxBounds.dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
      return;
    }
  });

  // Initialize Direct Manipulation
  initSubtitleDirectManipulation();
}

// ==========================================================================
// Storytelling Recap Studio (ស្ទូឌីយោសម្រាយរឿង) Events & Logic
// ==========================================================================
function bindRecapStudioEvents() {
  // Tab switcher triggers
  if (ui.tabTriggerRecap) {
    ui.tabTriggerRecap.addEventListener("click", () => switchStudioTab("recap"));
  }
  if (ui.btnSideToolbarRecap) {
    ui.btnSideToolbarRecap.addEventListener("click", () => switchStudioTab("recap"));
  }

  // 1. Narrative Mood / Style Cards
  if (ui.recapStyleGrid) {
    ui.recapStyleGrid.querySelectorAll(".recap-style-card").forEach((card) => {
      card.addEventListener("click", () => {
        ui.recapStyleGrid.querySelectorAll(".recap-style-card").forEach((c) => c.classList.remove("active"));
        card.classList.add("active");
        const style = card.dataset.style;
        appState.recapStudio.activeStyle = style;

        // Auto-match default BGM track to style
        if (ui.selectRecapBgm) {
          if (style === "youtube") ui.selectRecapBgm.value = "chill";
          else if (style === "suspense") ui.selectRecapBgm.value = "suspense";
          else if (style === "action") ui.selectRecapBgm.value = "action";
          else if (style === "drama") ui.selectRecapBgm.value = "emotional";
          else if (style === "humorous") ui.selectRecapBgm.value = "chill";
          appState.recapStudio.bgmTrack = ui.selectRecapBgm.value;
        }
        const styleTitle = card.querySelector(".style-title")?.textContent || style;
        showToast(`ជ្រើសរើសស្ទីលសម្រាយ៖ ${styleTitle}`);
      });
    });
  }

  // Script Options: Hook & CTA
  if (ui.chkRecapHook) {
    ui.chkRecapHook.addEventListener("change", (e) => {
      appState.recapStudio.includeHook = Boolean(e.target.checked);
    });
  }
  if (ui.chkRecapCta) {
    ui.chkRecapCta.addEventListener("change", (e) => {
      appState.recapStudio.includeCta = Boolean(e.target.checked);
    });
  }
  if (ui.chkRecapHybrid) {
    ui.chkRecapHybrid.addEventListener("change", (e) => {
      appState.recapStudio.hybridDialogue = Boolean(e.target.checked);
      if (appState.recapStudio.hybridDialogue) {
        showToast("🎭 បានបើក Hybrid Mode (ពន្យល់សាច់រឿង + តួអង្គនិយាយ)!");
      } else {
        showToast("🎙️ បានបិទ Hybrid Mode (Narrator តែម្នាក់)");
      }
    });
  }

  // Pacing & AI Model
  if (ui.selectRecapPacing) {
    ui.selectRecapPacing.addEventListener("change", (e) => {
      appState.recapStudio.pacing = e.target.value;
    });
  }
  if (ui.selectRecapModel) {
    ui.selectRecapModel.addEventListener("change", (e) => {
      appState.recapStudio.modelName = e.target.value;
    });
  }

  // 2. Voice Tone Presets & Master Narrator Settings
  const RECAP_TONE_PRESETS = {
    youtube_master: {
      name: "YouTube Master (ពិសិដ្ឋ 1.15x)",
      voice: "km-KH-PisethNeural",
      speed: 1.15,
      pitch: 0,
      volume: 70,
    },
    cinematic_deep: {
      name: "Cinematic Deep Male (ប្រុសគ្រលរធ្ងន់)",
      voice: "km-KH-PisethNeural",
      speed: 1.05,
      pitch: -5,
      volume: 85,
    },
    hype_fast: {
      name: "Hype Fast Storyteller (រស់រវើក ញាប់ 1.20x)",
      voice: "km-KH-PisethNeural",
      speed: 1.20,
      pitch: 1,
      volume: 80,
    },
    emotional_female: {
      name: "Emotional Female (ស្រីមុំ កម្សត់)",
      voice: "km-KH-SreymomNeural",
      speed: 1.05,
      pitch: -2,
      volume: 75,
    },
  };

  function applyRecapTonePreset(presetKey) {
    const preset = RECAP_TONE_PRESETS[presetKey];
    if (!preset) return;
    appState.recapStudio.tonePreset = presetKey;
    appState.recapStudio.voice = preset.voice;
    appState.recapStudio.speed = preset.speed;
    appState.recapStudio.pitch = preset.pitch;
    appState.recapStudio.volume = preset.volume;

    if (ui.selectRecapVoice) ui.selectRecapVoice.value = preset.voice;
    if (ui.rangeRecapSpeed) {
      ui.rangeRecapSpeed.value = preset.speed;
      if (ui.valRecapSpeed) ui.valRecapSpeed.textContent = `${preset.speed.toFixed(2)}x`;
    }
    if (ui.rangeRecapPitch) {
      ui.rangeRecapPitch.value = preset.pitch;
      if (ui.valRecapPitch) ui.valRecapPitch.textContent = `${preset.pitch >= 0 ? "+" : ""}${preset.pitch}Hz`;
    }
    if (ui.rangeRecapVolume) {
      ui.rangeRecapVolume.value = preset.volume;
      if (ui.valRecapVolume) ui.valRecapVolume.textContent = `+${preset.volume}%`;
    }

    if (ui.recapTonePresetsGrid) {
      ui.recapTonePresetsGrid.querySelectorAll(".btn-tone-preset").forEach((b) => {
        if (b.dataset.preset === presetKey) b.classList.add("active");
        else b.classList.remove("active");
      });
    }
    showToast(`🎙️ បានកំណត់ស្ទីលសំឡេង៖ ${preset.name}`);
  }

  if (ui.recapTonePresetsGrid) {
    ui.recapTonePresetsGrid.querySelectorAll(".btn-tone-preset").forEach((btn) => {
      btn.addEventListener("click", () => {
        applyRecapTonePreset(btn.dataset.preset);
      });
    });
  }

  if (ui.selectRecapVoice) {
    ui.selectRecapVoice.addEventListener("change", (e) => {
      appState.recapStudio.voice = e.target.value;
    });
  }
  if (ui.rangeRecapSpeed) {
    ui.rangeRecapSpeed.addEventListener("input", (e) => {
      const spd = parseFloat(e.target.value);
      appState.recapStudio.speed = spd;
      if (ui.valRecapSpeed) ui.valRecapSpeed.textContent = `${spd.toFixed(2)}x`;
    });
  }
  if (ui.rangeRecapVolume) {
    ui.rangeRecapVolume.addEventListener("input", (e) => {
      const vol = parseInt(e.target.value, 10);
      appState.recapStudio.volume = vol;
      if (ui.valRecapVolume) ui.valRecapVolume.textContent = `+${vol}%`;
    });
  }
  if (ui.rangeRecapPitch) {
    ui.rangeRecapPitch.addEventListener("input", (e) => {
      const pitch = parseInt(e.target.value, 10);
      appState.recapStudio.pitch = pitch;
      if (ui.valRecapPitch) ui.valRecapPitch.textContent = `${pitch >= 0 ? "+" : ""}${pitch}Hz`;
    });
  }

  // 3. Background Music (BGM) & Ducking Controls
  if (ui.selectRecapBgm) {
    ui.selectRecapBgm.addEventListener("change", (e) => {
      appState.recapStudio.bgmTrack = e.target.value;
      if (appState.recapStudio.isPlayingBgm) {
        playRecapBgmPreview(appState.recapStudio.bgmTrack);
      }
    });
  }
  if (ui.rangeRecapBgmVol) {
    ui.rangeRecapBgmVol.addEventListener("input", (e) => {
      const vol = parseInt(e.target.value, 10);
      appState.recapStudio.bgmVolume = vol;
      if (ui.valRecapBgmVol) ui.valRecapBgmVol.textContent = `${vol}%`;
      if (appState.recapStudio.bgmAudioEl) {
        appState.recapStudio.bgmAudioEl.volume = Math.max(0, Math.min(1, vol / 100));
      }
    });
  }
  if (ui.rangeRecapDuckedVol) {
    ui.rangeRecapDuckedVol.addEventListener("input", (e) => {
      const vol = parseInt(e.target.value, 10);
      appState.recapStudio.duckedVolume = vol;
      if (ui.valRecapDuckedVol) ui.valRecapDuckedVol.textContent = `${vol}%`;
    });
  }

  // BGM Preview Playback Toggle
  function stopRecapBgmPreview() {
    if (appState.recapStudio.bgmAudioEl) {
      appState.recapStudio.bgmAudioEl.pause();
      appState.recapStudio.bgmAudioEl = null;
    }
    appState.recapStudio.isPlayingBgm = false;
    if (ui.labelBgmPlay) ui.labelBgmPlay.textContent = "Preview";
    if (ui.iconBgmPlay) {
      ui.iconBgmPlay.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
    }
  }

  function playRecapBgmPreview(trackId) {
    stopRecapBgmPreview();
    const audio = new Audio(`/api/recap/bgm-file/${trackId}`);
    audio.loop = true;
    audio.volume = Math.max(0.05, Math.min(1, (appState.recapStudio.bgmVolume || 35) / 100));
    audio.play().then(() => {
      appState.recapStudio.bgmAudioEl = audio;
      appState.recapStudio.isPlayingBgm = true;
      if (ui.labelBgmPlay) ui.labelBgmPlay.textContent = "Stop";
      if (ui.iconBgmPlay) {
        ui.iconBgmPlay.innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
      }
    }).catch((err) => {
      console.warn("BGM preview play error:", err);
      showToast("មិនអាចចាក់ភ្លេង Preview បានទេ (BGM loading)");
      stopRecapBgmPreview();
    });
  }

  if (ui.btnRecapPreviewBgm) {
    ui.btnRecapPreviewBgm.addEventListener("click", () => {
      if (appState.recapStudio.isPlayingBgm) {
        stopRecapBgmPreview();
      } else {
        const trackId = appState.recapStudio.bgmTrack || (ui.selectRecapBgm && ui.selectRecapBgm.value) || "suspense";
        playRecapBgmPreview(trackId);
      }
    });
  }

  // Custom BGM Upload
  if (ui.inputCustomBgm) {
    ui.inputCustomBgm.addEventListener("change", async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      showToast(`កំពុង Upload បទភ្លេង "${file.name}"...`);
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await fetch("/api/recap/upload-bgm", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Upload failed");
        }
        const data = await res.json();
        if (ui.selectRecapBgm) {
          const opt = document.createElement("option");
          opt.value = data.id;
          opt.textContent = `🎵 ${data.name}`;
          opt.selected = true;
          ui.selectRecapBgm.appendChild(opt);
          appState.recapStudio.bgmTrack = data.id;
        }
        showToast("Upload ភ្លេង BGM ជោគជ័យ!");
      } catch (err) {
        console.error("Upload BGM error:", err);
        showToast(`បរាជ័យ Upload BGM: ${err.message}`);
      }
    });
  }

  // 4. 1-Click Movie Recap Presets
  if (ui.btnApplyRecap916) {
    ui.btnApplyRecap916.addEventListener("click", () => {
      if (typeof setCanvasAspectRatio === "function") {
        setCanvasAspectRatio("9:16");
      } else if (ui.selectCanvasAspect) {
        ui.selectCanvasAspect.value = "9:16";
        appState.blurSettings.aspectRatio = "9:16";
      }
      showToast("📱 កំណត់ Canvas 9:16 (TikTok/Reels/Shorts) រួចរាល់!");
    });
  }

  if (ui.btnApplyRecapBlurSub) {
    ui.btnApplyRecapBlurSub.addEventListener("click", () => {
      if (typeof setBlurStudioEnabled === "function") {
        setBlurStudioEnabled(true);
      }
      if (typeof applyBlurPreset === "function") {
        applyBlurPreset("bottom_banner");
      }
      const activeObj = appState.blurStudio.objects.find((o) => o.id === appState.blurStudio.activeBlurId);
      if (activeObj) {
        activeObj.x = 0.0;
        activeObj.y = 0.76;
        activeObj.width = 1.0;
        activeObj.height = 0.22;
        activeObj.blurType = "gaussian";
        activeObj.strength = 60;
        if (typeof syncBlurControlsFromState === "function") syncBlurControlsFromState();
        if (typeof updateBlurPreview === "function") updateBlurPreview(appState.currentTime);
      }
      showToast("🛡️ បានបិទបាំងអក្សររត់បរទេស និង Watermark ខាងក្រោម 100%!");
    });
  }

  if (ui.btnApplyRecapKinetic) {
    ui.btnApplyRecapKinetic.addEventListener("click", () => {
      pushSubtitleHistory("Recap Kinetic Preset");
      appState.subtitleStyle = {
        ...appState.subtitleStyle,
        preset: "yellow_bold",
        fontFamily: "Kantumruy Pro",
        fontSize: 34,
        fontWeight: "800",
        italic: false,
        uppercase: false,
        textColor: "#facc15",
        textOpacity: 100,
        strokeEnabled: true,
        strokeColor: "#000000",
        strokeWidth: 4,
        shadowEnabled: true,
        shadowColor: "rgba(0,0,0,0.8)",
        shadowBlur: 8,
        shadowOffsetX: 3,
        shadowOffsetY: 3,
        bgStyle: "semi",
        bgColor: "#000000",
        bgOpacity: 65,
        bgPadding: 10,
        bgRadius: 12,
        posX: 50,
        posY: 82,
        align: "center",
        entranceAnim: "pop",
        wordAnim: "highlightCurrent",
        karaokeColor: "#ffffff",
        karaokeSpeed: 1.0,
        langMode: "khmer",
      };
      syncSubtitleControlsFromState();
      updateVideoSubtitleOverlay(appState.currentTime);
      showToast("🔤 បានកំណត់ស្ទីលអក្សរ Kinetic Recap (ពណ៌លឿង ដិតច្បាស់)!");
    });
  }

  // 5. Generate Recap Script (/api/recap/generate)
  if (ui.btnGenerateRecapScript) {
    ui.btnGenerateRecapScript.addEventListener("click", async () => {
      if (!appState.sessionId && appState.subtitles.length === 0) {
        showToast("សូម Upload វីដេអូជាមុនសិន!");
        return;
      }

      if (appState.subtitles.length === 0) {
        showToast("កំពុងទាញយកសាច់រឿងពីសំឡេងដើម (Auto STT)...");
        await triggerAutoTranscription();
        if (appState.subtitles.length === 0) {
          showToast("មិនមានអត្ថបទដើមដើម្បីធ្វើសម្រាយរឿងទេ។");
          return;
        }
      }

      const originalBtnText = ui.labelGenerateRecapScript ? ui.labelGenerateRecapScript.textContent : "";
      if (ui.labelGenerateRecapScript) ui.labelGenerateRecapScript.textContent = "កំពុងសរសេរសម្រាយរឿងតាម AI...";
      ui.btnGenerateRecapScript.disabled = true;
      showToast("កំពុងសរសេរអត្ថបទសម្រាយរឿងបែបទី៣ ជាភាសាខ្មែរ...");

      try {
        const apiKey = localStorage.getItem("khmerdub_gemini_api_key") || "";
        const payload = {
          session_id: appState.sessionId,
          segments: appState.subtitles,
          total_duration: appState.duration || (ui.mainVideoPlayer ? ui.mainVideoPlayer.duration : 30.0),
          style: appState.recapStudio.activeStyle,
          include_hook: appState.recapStudio.includeHook,
          include_cta: appState.recapStudio.includeCta,
          hybrid_dialogue: appState.recapStudio.hybridDialogue !== false,
          narrator_voice: appState.recapStudio.voice || "km-KH-PisethNeural",
          pacing: appState.recapStudio.pacing,
          model_name: appState.recapStudio.modelName,
          api_key: apiKey,
        };

        const res = await fetch("/api/recap/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Script generation failed");
        }

        const data = await res.json();
        const newSegments = data.segments || [];
        if (newSegments.length > 0) {
          pushSubtitleHistory("Generate Movie Recap Script");
          appState.subtitles = sanitizeSubtitleTimelines(newSegments, 0.35, appState.duration);
          renderSubtitlesTable();
          renderTimelineBlocks();
          updateStatusMetrics();
          updateVideoSubtitleOverlay(appState.currentTime);
          showToast(`✨ បង្កើតអត្ថបទសម្រាយរឿងជោគជ័យ ចំនួន ${newSegments.length} វគ្គ!`);
        } else {
          showToast("មិនទទួលបានទិន្នន័យអត្ថបទសម្រាយទេ");
        }
      } catch (err) {
        console.error("Recap script error:", err);
        showToast(`កំហុសបង្កើតអត្ថបទសម្រាយ៖ ${err.message}`);
      } finally {
        if (ui.labelGenerateRecapScript) ui.labelGenerateRecapScript.textContent = originalBtnText || "បង្កើតអត្ថបទសម្រាយរឿង (Generate Script)";
        ui.btnGenerateRecapScript.disabled = false;
      }
    });
  }

  // 6. Synthesize Master Narrator Voice (/api/tts/synthesize-batch)
  if (ui.btnSynthesizeRecapAudio) {
    ui.btnSynthesizeRecapAudio.addEventListener("click", async () => {
      if (appState.subtitles.length === 0) {
        showToast("សូមបង្កើតអត្ថបទសម្រាយរឿងជាមុនសិន!");
        return;
      }

      const origText = ui.labelSynthesizeRecap ? ui.labelSynthesizeRecap.textContent : "";
      if (ui.labelSynthesizeRecap) ui.labelSynthesizeRecap.textContent = "កំពុងបញ្ចូលសំឡេង Narrator...";
      ui.btnSynthesizeRecapAudio.disabled = true;
      showToast("កំពុងបញ្ចូលសំឡេងអ្នកសម្រាយរឿង (Edge-TTS)...");

      try {
        const ratePct = Math.round((appState.recapStudio.speed - 1.0) * 100);
        const rateStr = `${ratePct >= 0 ? "+" : ""}${ratePct}%`;
        const volStr = `+${appState.recapStudio.volume}%`;
        const pitchStr = `${appState.recapStudio.pitch >= 0 ? "+" : ""}${appState.recapStudio.pitch}Hz`;

        const res = await fetch("/api/tts/all", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: appState.sessionId,
            segments: appState.subtitles,
            voice: appState.recapStudio.voice,
            rate: rateStr,
            pitch: pitchStr,
            volume: volStr,
            auto_adjust_duration: true,
          }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "TTS synthesis failed");
        }

        const data = await res.json();
        appState.subtitles = sanitizeSubtitleTimelines(data.segments || appState.subtitles, 0.25, appState.duration);
        renderSubtitlesTable();
        renderTimelineBlocks();
        updateStatusMetrics();
        showToast("🎙️ បញ្ចូលសំឡេងអ្នកសម្រាយរឿងគ្រប់វគ្គជោគជ័យ!");
      } catch (err) {
        console.error("Synthesize error:", err);
        showToast(`កំហុសបញ្ចូលសំឡេង៖ ${err.message}`);
      } finally {
        if (ui.labelSynthesizeRecap) ui.labelSynthesizeRecap.textContent = origText || "បញ្ចូលសំឡេង Narrator (Synthesize Audio)";
        ui.btnSynthesizeRecapAudio.disabled = false;
      }
    });
  }

  // 7. Render & Export Movie Recap Video (/api/dub with sidechain_ducking)
  if (ui.btnRenderRecapVideo) {
    ui.btnRenderRecapVideo.addEventListener("click", async () => {
      if (!appState.sessionId) {
        showToast("សូម Upload វីដេអូ និងបង្កើតសាច់រឿងជាមុនសិន!");
        return;
      }
      if (appState.subtitles.length === 0) {
        showToast("មិនទាន់មានអត្ថបទសម្រាយរឿងទេ។");
        return;
      }

      showToast("កំពុងដំណើរការ Export វីដេអូសម្រាយរឿងជាមួយ BGM & Auto-Ducking...");
      showPlayerLoading("Rendering Movie Recap Video with FFmpeg Sidechain Ducking...");
      ui.btnRenderRecapVideo.disabled = true;

      try {
        appState.subtitles = sanitizeSubtitleTimelines(appState.subtitles, 0.35);
        renderSubtitlesTable();
        renderTimelineBlocks();

        const payload = {
          session_id: appState.sessionId,
          segments: appState.subtitles,
          mode: "sidechain_ducking",
          bgm_id: appState.recapStudio.bgmTrack || "suspense",
          bgm_volume: (appState.recapStudio.bgmVolume || 35) / 100,
          ducking_volume: (appState.recapStudio.duckedVolume || 12) / 100,
          dub_volume: 1.4,
          aspect_ratio: appState.blurSettings.aspectRatio || "original",
          canvas_blur_strength: 25,
          blur_subtitles: appState.blurSettings.enabled,
          blur_objects: appState.blurStudio.objects || [],
          burn_subtitles: true,
          subtitle_style: appState.subtitleStyle,
          subtitle_language_mode: "khmer",
        };

        const res = await fetch("/api/dub", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Recap video rendering failed");
        }

        const data = await res.json();
        appState.dubbedVideoUrl = data.dubbed_video_url;
        appState.dubbedAudioUrl = data.dubbed_audio_url;

        if (data.dubbed_video_url) {
          ui.mainVideoPlayer.src = data.dubbed_video_url;
          ui.mainVideoPlayer.load();
        }

        if (ui.downloadVideoBtn) {
          ui.downloadVideoBtn.href = data.dubbed_video_url || "#";
          ui.downloadVideoBtn.download = `${appState.projectName}_recap.mp4`;
        }
        if (ui.downloadAudioBtn) {
          ui.downloadAudioBtn.href = data.dubbed_audio_url || "#";
          ui.downloadAudioBtn.download = `${appState.projectName}_recap_audio.mp3`;
        }
        if (ui.downloadKhmerAssBtn && data.khmer_ass_url) {
          ui.downloadKhmerAssBtn.href = data.khmer_ass_url;
          ui.downloadKhmerAssBtn.download = `${appState.projectName}_recap.ass`;
        }
        if (ui.downloadKhmerSrtBtn && data.khmer_srt_url) {
          ui.downloadKhmerSrtBtn.href = data.khmer_srt_url;
          ui.downloadKhmerSrtBtn.download = `${appState.projectName}_recap.srt`;
        }

        updateProjectStatus("Completed");
        showToast("🎉 Export វីដេអូសម្រាយរឿងសម្រេចជោគជ័យ ១០០%!");
        setTimeout(() => {
          openExportModal();
        }, 1000);
      } catch (err) {
        console.error("Export recap error:", err);
        showToast(`កំហុស Export វីដេអូ៖ ${err.message}`);
        updateProjectStatus("Draft");
      } finally {
        ui.btnRenderRecapVideo.disabled = false;
        hidePlayerLoading();
      }
    });
  }
}

// Live Subtitle Overlay Rendering with Styling, Positioning, and Karaoke Spans
function updateVideoSubtitleOverlay(currentTime) {
  if (!ui.videoSubtitleOverlay) return;

  if (!appState.subtitlesVisible || appState.subtitles.length === 0) {
    ui.videoSubtitleOverlay.style.display = "none";
    ui.videoSubtitleOverlay.classList.add("hidden");
    return;
  }

  // Find active subtitle or use selected subtitle in studio mode if paused
  let current = appState.subtitles.find((s) => currentTime >= s.start && currentTime <= s.end);
  const isEditingStudio = appState.activeStudioTab === "subtitles";
  if (!current && isEditingStudio && !appState.isPlaying && appState.activeSubtitleId) {
    current = appState.subtitles.find((s) => s.id === appState.activeSubtitleId);
  }

  if (!current || (!current.text && !current.khmer_text)) {
    ui.videoSubtitleOverlay.style.display = "none";
    ui.videoSubtitleOverlay.classList.add("hidden");
    return;
  }

  const style = appState.subtitleStyle || {};

  // Safe area overlay toggle
  if (ui.subtitleSafeAreaOverlay) {
    ui.subtitleSafeAreaOverlay.style.display = style.safeAreaEnabled ? "block" : "none";
  }

  // Language Mode: Khmer, Original, or Dual Stacked
  const mode = style.langMode || "khmer";
  const origText = current.text || "";
  const khmerText = current.khmer_text || "";

  // Set font family, size, weight, styling
  const family = style.fontFamily || "Kantumruy Pro";
  ui.videoSubtitleOverlay.style.fontFamily = `"${family}", 'Kantumruy Pro', 'Noto Sans Khmer', sans-serif`;
  ui.videoSubtitleOverlay.style.fontSize = `${style.fontSize || 28}px`;
  ui.videoSubtitleOverlay.style.fontWeight = style.fontWeight || "700";
  ui.videoSubtitleOverlay.style.fontStyle = style.italic ? "italic" : "normal";
  ui.videoSubtitleOverlay.style.textTransform = style.uppercase ? "uppercase" : "none";
  ui.videoSubtitleOverlay.style.letterSpacing = `${style.letterSpacing || 0}px`;
  ui.videoSubtitleOverlay.style.lineHeight = style.lineHeight || 1.4;
  ui.videoSubtitleOverlay.style.textAlign = style.align || "center";

  // Position and normalized coordinates
  ui.videoSubtitleOverlay.style.left = `${style.posX ?? 50}%`;
  ui.videoSubtitleOverlay.style.top = `${style.posY ?? 85}%`;
  ui.videoSubtitleOverlay.style.transform = `translate(-50%, -50%) rotate(${style.rotation || 0}deg)`;

  // Colors & text styling
  const textColor = style.textColor || "#ffffff";
  const textOpacity = (style.textOpacity ?? 100) / 100;
  ui.videoSubtitleOverlay.style.color = textColor;
  ui.videoSubtitleOverlay.style.opacity = textOpacity;

  // Stroke
  if (style.strokeEnabled && style.strokeWidth > 0) {
    const sw = style.strokeWidth;
    const sc = style.strokeColor || "#000000";
    ui.videoSubtitleOverlay.style.webkitTextStroke = `${sw}px ${sc}`;
  } else {
    ui.videoSubtitleOverlay.style.webkitTextStroke = "0px transparent";
  }

  // Drop Shadow
  let shadowCss = "";
  if (style.strokeEnabled && style.strokeWidth > 0) {
    const sw = Math.min(2, style.strokeWidth);
    const sc = style.strokeColor || "#000000";
    shadowCss = `-${sw}px -${sw}px 0 ${sc}, ${sw}px -${sw}px 0 ${sc}, -${sw}px ${sw}px 0 ${sc}, ${sw}px ${sw}px 0 ${sc}`;
  }
  if (style.shadowEnabled) {
    const drop = `${style.shadowOffsetX ?? 2}px ${style.shadowOffsetY ?? 2}px ${style.shadowBlur ?? 4}px ${style.shadowColor || "#000000"}`;
    shadowCss = shadowCss ? `${shadowCss}, ${drop}` : drop;
  }
  ui.videoSubtitleOverlay.style.textShadow = shadowCss || "none";

  // Background box styling
  if (style.bgStyle && style.bgStyle !== "none") {
    ui.videoSubtitleOverlay.style.backgroundColor = hexToRgba(style.bgColor || "#000000", style.bgOpacity ?? 60);
    const pad = style.bgPadding ?? 8;
    ui.videoSubtitleOverlay.style.padding = `${pad}px ${Math.round(pad * 1.5)}px`;
    const rad = style.bgRadius ?? 8;
    const isPill = style.bgStyle === "rounded" || style.bgStyle === "glass_pill";
    ui.videoSubtitleOverlay.style.borderRadius = `${isPill ? Math.max(20, rad * 2) : rad}px`;

    const isBlur = style.bgStyle === "blur" || style.bgStyle === "glass_pill";
    const blurPx = isBlur ? (style.bgBlur ?? 12) : 0;
    if (blurPx > 0) {
      ui.videoSubtitleOverlay.style.backdropFilter = `blur(${blurPx}px) saturate(180%)`;
      ui.videoSubtitleOverlay.style.webkitBackdropFilter = `blur(${blurPx}px) saturate(180%)`;
      ui.videoSubtitleOverlay.style.border = "1px solid rgba(255, 255, 255, 0.18)";
      ui.videoSubtitleOverlay.style.boxShadow = "0 8px 32px rgba(0, 0, 0, 0.35)";
    } else {
      ui.videoSubtitleOverlay.style.backdropFilter = "none";
      ui.videoSubtitleOverlay.style.webkitBackdropFilter = "none";
      ui.videoSubtitleOverlay.style.border = "none";
      ui.videoSubtitleOverlay.style.boxShadow = "none";
    }
  } else {
    ui.videoSubtitleOverlay.style.backgroundColor = "transparent";
    ui.videoSubtitleOverlay.style.padding = "0px";
    ui.videoSubtitleOverlay.style.borderRadius = "0px";
    ui.videoSubtitleOverlay.style.backdropFilter = "none";
    ui.videoSubtitleOverlay.style.webkitBackdropFilter = "none";
    ui.videoSubtitleOverlay.style.border = "none";
    ui.videoSubtitleOverlay.style.boxShadow = "none";
  }

  // Animation timing calculations
  const duration = Math.max(0.1, current.end - current.start);
  const elapsed = Math.max(0, currentTime - current.start);
  const progress = Math.max(0, Math.min(1, elapsed / duration));

  // Reset animation classes
  ui.videoSubtitleOverlay.classList.remove(
    "sub-anim-fadeIn", "sub-anim-slideUp", "sub-anim-slideDown", "sub-anim-slideLeft",
    "sub-anim-slideRight", "sub-anim-scale", "sub-anim-pop", "sub-anim-typewriter",
    "sub-anim-fadeOut"
  );

  if (style.entranceAnim && style.entranceAnim !== "none" && progress < 0.25) {
    ui.videoSubtitleOverlay.classList.add(`sub-anim-${style.entranceAnim}`);
  } else if (style.exitAnim && style.exitAnim !== "none" && progress > 0.8) {
    ui.videoSubtitleOverlay.classList.add(`sub-anim-${style.exitAnim}`);
  }

  // Word Animation / Karaoke progressive rendering
  function renderAnimatedWords(text) {
    if (!text) return "";
    if (!style.wordAnim || style.wordAnim === "none") {
      return escapeHtml(text);
    }
    const words = tokenizeWords(text);
    if (words.length === 0) return escapeHtml(text);

    const activeWordIdx = Math.min(words.length - 1, Math.floor(progress * words.length));
    const kColor = style.karaokeColor || "#facc15";

    return words
      .map((w, idx) => {
        let wordClass = "sub-word";
        let inlineStyle = "";
        if (style.wordAnim === "highlightCurrent") {
          if (idx === activeWordIdx) {
            wordClass += " word-highlight-active";
            inlineStyle = `color: ${kColor}; font-weight: 800;`;
          }
        } else if (style.wordAnim === "karaoke") {
          if (idx <= activeWordIdx) {
            wordClass += " karaoke-word-fill active";
            inlineStyle = `color: ${kColor}; text-shadow: 0 0 8px ${kColor};`;
          } else {
            wordClass += " karaoke-word-fill";
          }
        } else if (style.wordAnim === "wordByWord") {
          if (idx > activeWordIdx) {
            inlineStyle = "opacity: 0;";
          }
        }
        return `<span class="${wordClass}" style="${inlineStyle}">${escapeHtml(w)}</span>`;
      })
      .join(" ");
  }

  // Render Subtitle Text Content
  if (mode === "dual") {
    ui.videoSubOrig.innerHTML = renderAnimatedWords(origText);
    ui.videoSubKhmer.innerHTML = renderAnimatedWords(khmerText || origText);
    ui.videoSubOrig.style.display = origText ? "block" : "none";
    ui.videoSubOrig.style.fontSize = "0.78em";
    ui.videoSubOrig.style.opacity = "0.85";
    ui.videoSubKhmer.style.display = "block";
    ui.videoSubKhmer.style.marginTop = "4px";
  } else if (mode === "orig") {
    ui.videoSubOrig.innerHTML = renderAnimatedWords(origText || khmerText);
    ui.videoSubOrig.style.display = "block";
    ui.videoSubOrig.style.fontSize = "1em";
    ui.videoSubOrig.style.opacity = "1";
    ui.videoSubKhmer.style.display = "none";
  } else {
    // Default: Khmer only
    ui.videoSubOrig.style.display = "none";
    ui.videoSubKhmer.innerHTML = renderAnimatedWords(khmerText || origText);
    ui.videoSubKhmer.style.display = "block";
    ui.videoSubKhmer.style.marginTop = "0px";
  }

  // Active selection box & inspection handle visibility
  if (isEditingStudio) {
    ui.videoSubtitleOverlay.classList.add("active-selected");
    if (ui.subSelectionTag) {
      ui.subSelectionTag.style.display = "flex";
      if (ui.subSelectionLabel) {
        ui.subSelectionLabel.textContent = `${current.speaker || "Subtitle"} (${formatTimecodeSimple(current.start)} - ${formatTimecodeSimple(current.end)})`;
      }
    }
  } else {
    ui.videoSubtitleOverlay.classList.remove("active-selected");
    if (ui.subSelectionTag) {
      ui.subSelectionTag.style.display = "none";
    }
  }

  ui.videoSubtitleOverlay.style.display = "flex";
  ui.videoSubtitleOverlay.classList.remove("hidden");

  // Synchronize Quick Editor in Studio Sidebar
  syncSubtitleQuickEditor(current);
}

function highlightActiveTableRowAndTimeline(currentTime) {
  const current = appState.subtitles.find((s) => currentTime >= s.start && currentTime <= s.end);
  if (!current) return;

  if (appState.activeSubtitleId !== current.id) {
    appState.activeSubtitleId = current.id;

    document.querySelectorAll(".subtitles-data-table tbody tr").forEach((tr) => {
      tr.classList.remove("row-active");
    });
    const activeRow = document.getElementById(`sub-row-${current.id}`);
    if (activeRow) {
      activeRow.classList.add("row-active");
    }

    document.querySelectorAll(".timeline-block").forEach((b) => b.classList.remove("block-active"));
    const activeBlock = document.getElementById(`time-block-${current.id}`);
    if (activeBlock) {
      activeBlock.classList.add("block-active");
    }
  }
}

// Intelligently stitch incomplete speech fragments into coherent, natural dialogue sentences
function smartMergeDialogueFragments(subtitles, maxGap = 0.55, maxDur = 4.2) {
  if (!Array.isArray(subtitles) || subtitles.length === 0) return [];
  const dangling = new Set([
    "i", "you", "he", "she", "we", "they", "it", "my", "your", "his", "her", "our", "their",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "that", "this", "these", "those", "a", "an", "the",
    "and", "but", "or", "so", "because", "if", "though", "although", "while", "as", "than",
    "to", "for", "with", "in", "on", "at", "from", "by", "of", "about", "into", "through",
    "is", "are", "was", "were", "am", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
    "not", "just", "really", "very"
  ]);
  const termRegex = /[.!?។៕…]+$/;
  const merged = [];

  for (const seg of subtitles) {
    const text = (seg.text || "").trim();
    if (!text) continue;
    const start = parseFloat(seg.start || 0);
    const end = parseFloat(seg.end || start + 0.5);

    if (merged.length > 0) {
      const prev = merged[merged.length - 1];
      const prevText = (prev.text || "").trim();
      const prevWords = prevText.split(/\s+/);
      const currWords = text.split(/\s+/);
      const gap = Math.round((start - prev.end) * 100) / 100;
      const combinedDur = Math.round((end - prev.start) * 100) / 100;
      const totalWords = prevWords.length + currWords.length;

      const prevHasPunct = termRegex.test(prevText);
      const lastWord = (prevWords[prevWords.length - 1] || "").toLowerCase().replace(/[^\w]/g, "");
      const isDangling = lastWord in dangling || dangling.has(lastWord);
      const isCapital = text[0] ? text[0] === text[0].toUpperCase() && text[0] !== text[0].toLowerCase() : false;
      const isContinuation = text[0] ? text[0] === text[0].toLowerCase() && text[0] !== text[0].toUpperCase() : false;
      const sameSpeaker = (prev.speaker || "Speaker 1") === (seg.speaker || "Speaker 1");

      // Strict dialogue separation:
      // Never merge if previous ended with punctuation or next starts with capital with pause >= 0.35s
      let shouldMerge = false;
      if (sameSpeaker && combinedDur <= maxDur && totalWords <= 12 && gap <= maxGap) {
        if (!prevHasPunct) {
          if (isDangling) {
            shouldMerge = true;
          } else if (isContinuation && gap <= 0.40) {
            shouldMerge = true;
          } else if (!isCapital && gap <= 0.30) {
            shouldMerge = true;
          }
        }
      }

      if (shouldMerge) {
        prev.text = `${prevText} ${text}`.trim();
        prev.end = Math.max(prev.end, end);
        if (seg.khmer_text) {
          prev.khmer_text = prev.khmer_text ? `${prev.khmer_text} ${seg.khmer_text}`.trim() : seg.khmer_text;
        }
        continue;
      }
    }

    merged.push({ ...seg, start, end, text });
  }

  return merged.map((s, idx) => ({ ...s, id: idx + 1 }));
}

// Guarantee strict collision-free timestamps so voices never talk over each other
// and all scene segments are preserved and accurately matched within original video duration
function sanitizeSubtitleTimelines(subtitles, minGap = 0.05, maxDuration = null, distributeEvenly = false) {
  if (!Array.isArray(subtitles) || subtitles.length === 0) return [];

  let effectiveMaxDur = (maxDuration && maxDuration > 0)
    ? maxDuration
    : (typeof appState !== 'undefined' && appState.duration > 0 ? appState.duration : null);

  if (!effectiveMaxDur && typeof ui !== 'undefined' && ui.mainVideoPlayer && ui.mainVideoPlayer.duration > 0) {
    effectiveMaxDur = ui.mainVideoPlayer.duration;
  }

  const limitDur = (effectiveMaxDur && effectiveMaxDur > 0) ? Math.floor(effectiveMaxDur * 100) / 100 : null;

  const sorted = [...subtitles]
    .map((s, idx) => ({ ...s, _idx: idx }))
    .sort((a, b) => {
      const aStart = parseFloat(a.start) || 0;
      const bStart = parseFloat(b.start) || 0;
      if (Math.abs(aStart - bStart) > 0.001) return aStart - bStart;
      return a._idx - b._idx;
    });

  const numSegs = sorted.length;

  // Only distribute evenly if explicitly requested (e.g. for synthetic recap timeline slots)
  if (distributeEvenly && limitDur && limitDur > 3.0 && numSegs > 0) {
    const maxEndTime = Math.round((limitDur - 0.25) * 100) / 100;
    const slotLen = maxEndTime / numSegs;
    const pause = Math.min(minGap, Math.max(0.12, slotLen * 0.08));
    const speechDur = Math.round((slotLen - pause) * 100) / 100;

    return sorted.map((s, idx) => {
      const start = Math.round(idx * slotLen * 100) / 100;
      let end = Math.round((start + speechDur) * 100) / 100;
      if (idx === numSegs - 1) {
        end = maxEndTime;
      }
      const copy = { ...s };
      delete copy._idx;
      copy.id = idx + 1;
      copy.start = start;
      copy.end = end;
      return copy;
    });
  }

  // Preserve character speech timing — resolve collisions by trimming PREVIOUS segment's
  // end (not by pushing current segment's start forward, which destroys Whisper's word timing)
  const cleaned = [];
  let prevEnd = 0.0;

  for (let i = 0; i < sorted.length; i++) {
    const s = sorted[i];
    let rawStart = Math.max(0, parseFloat(s.start) || 0);
    let rawEnd = parseFloat(s.end);
    if (isNaN(rawEnd) || rawEnd <= rawStart) {
      rawEnd = rawStart + 1.0;
    }

    const wordCount = (s.text || s.khmer_text || "").trim().split(/\s+/).length;
    const speechRoomNeeded = wordCount >= 3 ? Math.max(2.2, Math.min(wordCount * 0.45, 4.0)) : 1.2;

    let safeStart = Math.round(rawStart * 100) / 100;
    let safeEnd = Math.round(Math.max(safeStart + 0.25, rawEnd) * 100) / 100;

    // Strict boundary clamping if limitDur is specified
    if (limitDur && limitDur > 0) {
      if (safeEnd > limitDur) {
        safeEnd = limitDur;
      }
      if (safeStart >= safeEnd) {
        safeStart = Math.round(Math.max(0, safeEnd - 0.25) * 100) / 100;
      }
    }

    // Resolve overlap with previous segment by trimming previous segment's end
    if (cleaned.length > 0 && safeStart < prevEnd) {
      const prevSeg = cleaned[cleaned.length - 1];
      const trimmedEnd = Math.max(
        prevSeg.start + 1.0,
        Math.round((safeStart - minGap) * 100) / 100
      );
      prevSeg.end = trimmedEnd;
      prevEnd = trimmedEnd;
      safeStart = Math.round((prevSeg.end + minGap) * 100) / 100;
    }

    if (limitDur && limitDur > 0 && safeEnd > limitDur) {
      safeEnd = limitDur;
    }

    prevEnd = safeEnd;

    const copy = { ...s };
    delete copy._idx;
    delete copy._validationState;
    copy.id = i + 1;
    copy.start = safeStart;
    copy.end = safeEnd;
    cleaned.push(copy);
  }

  // Absolute hard clamp: no segment can EVER exceed limitDur and adjacent segments never overlap
  for (let idx = 0; idx < cleaned.length; idx++) {
    cleaned[idx].id = idx + 1;
    let sEnd = Math.round((parseFloat(cleaned[idx].end) || 0) * 100) / 100;
    let sStart = Math.round((parseFloat(cleaned[idx].start) || 0) * 100) / 100;

    if (limitDur && limitDur > 0) {
      sEnd = Math.min(limitDur, sEnd);
      sStart = Math.min(Math.max(0, sStart), Math.max(0, sEnd - 0.2));
    }

    if (idx + 1 < cleaned.length) {
      const nextStart = Math.round((parseFloat(cleaned[idx + 1].start) || 0) * 100) / 100;
      const maxAllowedEnd = Math.round((nextStart - minGap) * 100) / 100;
      if (sEnd > maxAllowedEnd) {
        sEnd = Math.max(Math.round((sStart + 0.2) * 100) / 100, maxAllowedEnd);
      }
    }

    cleaned[idx].start = sStart;
    cleaned[idx].end = sEnd;
  }

  return cleaned;
}

function prepareSegmentsForApi(segments) {
  if (!Array.isArray(segments)) return [];
  return segments.map((s) => {
    const copy = { ...s };
    delete copy._validationState;
    delete copy._idx;
    return copy;
  });
}

// ==========================================================================
// Timeline Validation Service
// Centralized: detectOverflow, detectCollision, autoFix, undo, validateBeforeExport
// ==========================================================================
const TimelineValidator = {

  detectOverflow(sub, videoDuration) {
    if (!videoDuration || videoDuration <= 0) return { detected: false, amount: 0 };
    const end = parseFloat(sub.end) || 0;
    const amount = Math.round((end - videoDuration) * 100) / 100;
    return { detected: amount > 0.005, amount: Math.max(0, amount) };
  },

  detectCollision(sub, allSubs) {
    if (!Array.isArray(allSubs)) return { detected: false, with: null, overlapAmt: 0 };
    const start = parseFloat(sub.start) || 0;
    const end = parseFloat(sub.end) || 0;
    for (const other of allSubs) {
      if (other.id === sub.id) continue;
      const oStart = parseFloat(other.start) || 0;
      const oEnd = parseFloat(other.end) || 0;
      if (start < oEnd && end > oStart) {
        const overlapAmt = Math.round((Math.min(end, oEnd) - Math.max(start, oStart)) * 100) / 100;
        if (overlapAmt > 0.01) {
          return {
            detected: true,
            with: { id: other.id, start: oStart, end: oEnd },
            overlapAmt,
          };
        }
      }
    }
    return { detected: false, with: null, overlapAmt: 0 };
  },

  validateSubtitle(sub, videoDuration, allSubs) {
    const overflow = this.detectOverflow(sub, videoDuration);
    const collision = this.detectCollision(sub, allSubs || []);
    const start = parseFloat(sub.start) || 0;
    const end = parseFloat(sub.end) || 0;
    const negativeDuration = end <= start;
    const startsBefore = start < 0;
    let voiceTooLong = false;
    let voiceOverflow = 0;
    if (sub.tts_duration && sub.tts_duration > 0) {
      const available = end - start;
      voiceOverflow = Math.round((sub.tts_duration - available) * 100) / 100;
      voiceTooLong = voiceOverflow > 0.05;
    }
    const hasIssue = overflow.detected || collision.detected || negativeDuration || startsBefore || voiceTooLong;
    const isCritical = overflow.detected || negativeDuration || startsBefore;
    return {
      overflow: overflow.detected, overflowAmt: overflow.amount,
      collision: collision.detected, collisionWith: collision.with, collisionAmt: collision.overlapAmt,
      voiceTooLong, voiceOverflow,
      negativeDuration, startsBefore,
      hasIssue, isCritical,
    };
  },

  validateTimeline(subtitles, videoDuration) {
    if (!Array.isArray(subtitles)) return { issues: [], hasBlocker: false };
    const issues = [];
    let hasBlocker = false;
    subtitles.forEach(sub => {
      const v = this.validateSubtitle(sub, videoDuration, subtitles);
      if (v.hasIssue) {
        issues.push({ sub, ...v });
        if (v.isCritical) hasBlocker = true;
      }
    });
    return { issues, hasBlocker };
  },

  autoFixOverflow(sub, videoDuration) {
    if (sub._originalEnd === undefined) sub._originalEnd = sub.end;
    if (sub._originalStart === undefined) sub._originalStart = sub.start;
    sub.end = Math.round(videoDuration * 100) / 100;
    if (sub.end <= parseFloat(sub.start)) {
      sub.start = Math.max(0, Math.round((videoDuration - 1.0) * 100) / 100);
    }
    sub.syncStatus = 'auto_fixed';
    sub.needsReview = true;
    sub.status = 'Needs Review';
  },

  autoFixCollision(subA, subB, minGap = 0.05) {
    if (subA._originalEnd === undefined) subA._originalEnd = subA.end;
    const bStart = parseFloat(subB.start) || 0;
    subA.end = Math.max(
      (parseFloat(subA.start) || 0) + 0.25,
      Math.round((bStart - minGap) * 100) / 100
    );
    subA.syncStatus = 'auto_fixed';
    subA.needsReview = true;
    subA.status = 'Needs Review';
  },

  autoFixAll(subtitles, videoDuration, minGap = 0.05) {
    const sorted = [...subtitles].sort((a, b) => (parseFloat(a.start) || 0) - (parseFloat(b.start) || 0));
    for (let i = 0; i < sorted.length; i++) {
      const sub = sorted[i];
      if (i > 0) {
        const prev = sorted[i - 1];
        const prevEnd = parseFloat(prev.end) || 0;
        const curStart = parseFloat(sub.start) || 0;
        if (curStart < prevEnd) this.autoFixCollision(prev, sub, minGap);
      }
      const ov = this.detectOverflow(sub, videoDuration);
      if (ov.detected) this.autoFixOverflow(sub, videoDuration);
    }
    return subtitles;
  },

  undoFix(sub) {
    if (sub._originalEnd !== undefined) { sub.end = sub._originalEnd; delete sub._originalEnd; }
    if (sub._originalStart !== undefined) { sub.start = sub._originalStart; delete sub._originalStart; }
    sub.syncStatus = null;
    sub.needsReview = false;
    if (sub.status === 'Needs Review') sub.status = 'Ready';
  },

  validateBeforeExport(subtitles, videoDuration) {
    const { issues } = this.validateTimeline(subtitles, videoDuration);
    const blockers = issues.filter(i => i.isCritical);
    return { canExport: blockers.length === 0, blockers, warnings: issues.filter(i => !i.isCritical) };
  },
};

// ==========================================================================
// 3. Subtitle Data Table & In-Place Editing
// ==========================================================================
function getFilteredSubtitles() {
  return appState.subtitles.filter((sub) => {
    const matchesFilter = appState.statusFilter === "all" || sub.status === appState.statusFilter;
    if (!matchesFilter) return false;
    if (!appState.searchQuery) return true;

    const q = appState.searchQuery;
    const startStr = formatTimecodePrecise(sub.start || 0).toLowerCase();
    const endStr = formatTimecodePrecise(sub.end || 0).toLowerCase();

    return (
      (sub.text && sub.text.toLowerCase().includes(q)) ||
      (sub.khmer_text && sub.khmer_text.toLowerCase().includes(q)) ||
      (sub.speaker && sub.speaker.toLowerCase().includes(q)) ||
      startStr.includes(q) ||
      endStr.includes(q) ||
      String(sub.id) === q.replace(/^#/, "")
    );
  });
}

function renderSubtitlesTable() {
  if (appState.duration > 0 && Array.isArray(appState.subtitles) && appState.subtitles.length > 0) {
    const limit = Math.floor(appState.duration * 100) / 100;
    appState.subtitles.forEach((s) => {
      const e = parseFloat(s.end) || 0;
      if (e > limit) {
        s.end = limit;
      }
      const st = parseFloat(s.start) || 0;
      if (st >= limit) {
        s.start = Math.max(0, Math.round((limit - 0.5) * 100) / 100);
      }
    });
  }

  const filtered = getFilteredSubtitles();
  const totalPages = Math.max(1, Math.ceil(filtered.length / appState.pageSize));
  appState.currentPage = Math.min(appState.currentPage, totalPages);

  const startIdx = (appState.currentPage - 1) * appState.pageSize;
  const pageItems = filtered.slice(startIdx, startIdx + appState.pageSize);

  ui.subtitlesTableBody.innerHTML = "";
  ui.subtitlesSummaryCount.textContent = `${appState.subtitles.length} subtitles`;
  ui.pagTotalCount.textContent = `${appState.subtitles.length} subtitles`;

  if (appState.subtitles.length === 0) {
    ui.subtitlesTableBody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; padding: 3.5rem 1.5rem; color: var(--text-tertiary);">
          <div class="table-empty-state-wrap">
            <div class="table-empty-icon-circle">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </div>
            <h4 class="table-empty-title">No Subtitles Yet</h4>
            <p class="table-empty-desc">Upload a video and auto-generate AI dialogue transcription or import existing subtitles.</p>
            <div class="table-empty-actions-row">
              <button type="button" class="btn-sub-ctrl highlight-btn" onclick="addNewSubtitleSegment()">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                <span>Add Subtitle</span>
              </button>
              <button type="button" class="btn-sub-ctrl" onclick="triggerAutoTranscription()">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                </svg>
                <span>Auto Generate</span>
              </button>
              <button type="button" class="btn-sub-ctrl" onclick="document.getElementById('hiddenSrtImport').click()">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                <span>Import SRT</span>
              </button>
            </div>
          </div>
        </td>
      </tr>
    `;
    renderPagination(1, 1);
    return;
  }

  pageItems.forEach((sub, index) => {
    const tr = document.createElement("tr");
    tr.id = `sub-row-${sub.id}`;
    if (appState.activeSubtitleId === sub.id) {
      tr.classList.add("row-active");
    }
    if (sub.locked) {
      tr.classList.add("row-locked");
    }

    // Timeline validation for this subtitle
    const _valState = TimelineValidator.validateSubtitle(sub, appState.duration, appState.subtitles);
    if (_valState.overflow) tr.classList.add("row-overflow");
    else if (_valState.collision) tr.classList.add("row-collision");
    if (_valState.voiceTooLong) tr.classList.add("row-voice-long");

    const rowNum = startIdx + index + 1;
    const statusClass =
      sub.status === "Ready" ? "status-ready" : sub.status === "Needs Review" ? "status-review" : "status-translated";

    // Resolve speaker & voice reliably to prevent label mismatch
    const rawSpk = (sub.speaker || "").trim();
    const rawVoice = (sub.voice || "").trim();

    let selectedSpeaker = "Speaker 1";
    if (rawSpk === "Speaker 3 (Girl)" || rawSpk.toLowerCase().includes("girl") || rawVoice === "Khmer Girl 01") {
      selectedSpeaker = "Speaker 3 (Girl)";
    } else if (rawSpk === "Speaker 3 (Boy)" || rawSpk.toLowerCase().includes("boy") || rawVoice === "Khmer Boy 01") {
      selectedSpeaker = "Speaker 3 (Boy)";
    } else if (rawSpk === "Speaker 2" || rawSpk.toLowerCase().includes("female") || rawVoice === "Khmer Female 01" || rawSpk.toLowerCase().includes("woman")) {
      selectedSpeaker = "Speaker 2";
    } else if (rawSpk === "Narrator") {
      selectedSpeaker = "Narrator";
    } else {
      selectedSpeaker = "Speaker 1";
    }

    let selectedVoice = "Khmer Male 01";
    if (rawVoice === "Khmer Female 01" || selectedSpeaker === "Speaker 2") {
      selectedVoice = "Khmer Female 01";
    } else if (rawVoice === "Khmer Girl 01" || selectedSpeaker === "Speaker 3 (Girl)") {
      selectedVoice = "Khmer Girl 01";
    } else if (rawVoice === "Khmer Boy 01" || selectedSpeaker === "Speaker 3 (Boy)") {
      selectedVoice = "Khmer Boy 01";
    } else {
      selectedVoice = "Khmer Male 01";
    }

    // Keep sub state synchronized
    sub.speaker = selectedSpeaker;
    sub.voice = selectedVoice;

    // Visual Speaker Pill configuration
    let pillClass = "pill-male";
    let pillIcon = "👨";
    let pillText = "Speaker 1 (Male)";

    if (selectedSpeaker === "Speaker 2") {
      pillClass = "pill-female";
      pillIcon = "👩";
      pillText = "Speaker 2 (Female)";
    } else if (selectedSpeaker === "Speaker 3 (Boy)") {
      pillClass = "pill-boy";
      pillIcon = "👦";
      pillText = "Speaker 3 (Boy)";
    } else if (selectedSpeaker === "Speaker 3 (Girl)") {
      pillClass = "pill-girl";
      pillIcon = "👧";
      pillText = "Speaker 3 (Girl)";
    } else if (selectedSpeaker === "Narrator") {
      pillClass = "pill-narrator";
      pillIcon = "🎙️";
      pillText = "Narrator";
    }

    // Visual Emotion Pill configuration
    const rawEmotion = (sub.emotion || "neutral").trim().toLowerCase();
    let emotionClass = "pill-neutral";
    let emotionIcon = "😐";
    let emotionText = "Neutral (ធម្មតា)";

    if (rawEmotion === "whisper") {
      emotionClass = "pill-whisper";
      emotionIcon = "🤫";
      emotionText = "Whisper (ខ្សឹប)";
    } else if (rawEmotion === "angry" || rawEmotion === "shout") {
      emotionClass = "pill-angry";
      emotionIcon = "😡";
      emotionText = "Angry (ខឹង/ស្រែក)";
    } else if (rawEmotion === "sad" || rawEmotion === "crying") {
      emotionClass = "pill-sad";
      emotionIcon = "😭";
      emotionText = "Sad (យំសោក)";
    } else if (rawEmotion === "excited" || rawEmotion === "happy") {
      emotionClass = "pill-excited";
      emotionIcon = "🤩";
      emotionText = "Excited (រំភើប)";
    } else if (rawEmotion === "terrified" || rawEmotion === "fear") {
      emotionClass = "pill-terrified";
      emotionIcon = "😨";
      emotionText = "Terrified (ភ័យខ្លាច)";
    } else if (rawEmotion === "romantic" || rawEmotion === "sensual") {
      emotionClass = "pill-romantic";
      emotionIcon = "🥰";
      emotionText = "Romantic (ផ្អែមល្ហែម)";
    } else if (rawEmotion === "suspense" || rawEmotion === "mystery") {
      emotionClass = "pill-suspense";
      emotionIcon = "🔮";
      emotionText = "Suspense (អាថ៌កំបាំង)";
    } else if (rawEmotion === "sarcastic" || rawEmotion === "smirk") {
      emotionClass = "pill-sarcastic";
      emotionIcon = "😏";
      emotionText = "Sarcastic (បញ្ចើច/ឌឺដង)";
    } else if (rawEmotion === "exhausted" || rawEmotion === "tired") {
      emotionClass = "pill-exhausted";
      emotionIcon = "😮‍💨";
      emotionText = "Exhausted (ហត់នឿយ)";
    }

    const isRowPlaying = appState.activeAudioRowId === sub.id;
    const isRowLoading = appState.loadingAudioRowId === sub.id;

    tr.innerHTML = `
      <td class="col-num">
        <div class="col-num-cell-wrap">
          <input type="checkbox" class="sub-checkbox sub-row-checkbox" data-id="${sub.id}" ${sub.selected ? 'checked' : ''} title="Select subtitle #${rowNum} for dubbing" onchange="toggleSelectSubtitle(${sub.id}, this.checked, event)" />
          <span class="sub-index-num">${rowNum}</span>
        </div>
      </td>
      <td class="col-start">
        <input class="time-edit-input" type="text" value="${formatTimecodePrecise(sub.start)}" 
               title="Click to edit start timestamp" onchange="onEditTimestamp(${sub.id}, 'start', this.value)" />
      </td>
      <td class="col-end">
        <input class="time-edit-input ${_valState.overflow ? 'input-overflow' : _valState.collision ? 'input-collision' : ''}" type="text" value="${formatTimecodePrecise(sub.end)}" 
               title="Click to edit end timestamp" onchange="onEditTimestamp(${sub.id}, 'end', this.value)" />
        ${_valState.overflow ? `<div class="timeline-issue-badge overflow-badge" title="Subtitle extends ${_valState.overflowAmt.toFixed(2)}s beyond video end">⚠ +${_valState.overflowAmt.toFixed(2)}s</div>` : ''}
        ${_valState.collision ? `<div class="timeline-issue-badge collision-badge" title="Overlaps ${_valState.collisionAmt.toFixed(2)}s with subtitle #${_valState.collisionWith ? _valState.collisionWith.id : '?'}">⚠ OVERLAP</div>` : ''}
        ${_valState.voiceTooLong ? `<div class="timeline-issue-badge voice-long-badge" title="TTS ${(sub.tts_duration || 0).toFixed(2)}s > slot ${((parseFloat(sub.end) || 0) - (parseFloat(sub.start) || 0)).toFixed(2)}s">⚠ Voice Long</div>` : ''}
      </td>
      <td class="col-orig">
        <textarea class="table-text-cell" rows="1" 
                  title="Click to edit original text" onchange="onEditText(${sub.id}, 'text', this.value)">${escapeHtml(sub.text || '')}</textarea>
      </td>
      <td class="col-khmer">
        <textarea class="table-text-cell khmer-cell" rows="1" 
                  title="Click to edit Khmer translation" onchange="onEditText(${sub.id}, 'khmer_text', this.value)">${escapeHtml(sub.khmer_text || '')}</textarea>
        <div style="display:flex;align-items:center;gap:5px;margin-top:2px;">
          ${sub.provider ? `<span class="row-provider-pill">${escapeHtml(sub.provider.toUpperCase())}</span>` : ''}
          ${sub.tone && sub.tone !== 'neutral' ? `<span class="row-tone-badge">${escapeHtml(sub.tone)}</span>` : ''}
          ${sub.pacing && sub.pacing !== 'normal' ? `<span class="row-pacing-badge pacing-${escapeHtml(sub.pacing)}">⚡ ${escapeHtml(sub.pacing.toUpperCase())}</span>` : ''}
        </div>
      </td>
      <td class="col-speaker">
        <div class="speaker-select-cell-wrap" title="Click to change character speaker">
          <div class="speaker-pill ${pillClass}">
            <span class="pill-avatar">${pillIcon}</span>
            <span class="pill-label">${escapeHtml(pillText)}</span>
            <span class="pill-chevron">▼</span>
          </div>
          <select class="native-select-overlay" onchange="onEditSelect(${sub.id}, 'speaker', this.value)">
            <option value="Speaker 1" ${selectedSpeaker === "Speaker 1" ? "selected" : ""}>👨 Speaker 1 (Male)</option>
            <option value="Speaker 2" ${selectedSpeaker === "Speaker 2" ? "selected" : ""}>👩 Speaker 2 (Female)</option>
            <option value="Speaker 3 (Boy)" ${selectedSpeaker === "Speaker 3 (Boy)" ? "selected" : ""}>👦 Speaker 3 (Boy)</option>
            <option value="Speaker 3 (Girl)" ${selectedSpeaker === "Speaker 3 (Girl)" ? "selected" : ""}>👧 Speaker 3 (Girl)</option>
            <option value="Narrator" ${selectedSpeaker === "Narrator" ? "selected" : ""}>🎙️ Narrator</option>
          </select>
        </div>
      </td>
      <td class="col-emotion">
        <div class="emotion-select-cell-wrap" title="Click to change character emotion & expression">
          <div class="emotion-pill ${emotionClass}">
            <span class="pill-avatar">${emotionIcon}</span>
            <span class="pill-label">${escapeHtml(emotionText)}</span>
            <span class="pill-chevron">▼</span>
          </div>
          <select class="native-select-overlay" onchange="onEditSelect(${sub.id}, 'emotion', this.value)">
            <option value="neutral" ${rawEmotion === "neutral" ? "selected" : ""}>😐 Neutral (ធម្មតា)</option>
            <option value="whisper" ${rawEmotion === "whisper" ? "selected" : ""}>🤫 Whisper (ខ្សឹប)</option>
            <option value="angry" ${rawEmotion === "angry" || rawEmotion === "shout" ? "selected" : ""}>😡 Angry (ខឹង/ស្រែក)</option>
            <option value="sad" ${rawEmotion === "sad" || rawEmotion === "crying" ? "selected" : ""}>😭 Sad (យំសោក)</option>
            <option value="excited" ${rawEmotion === "excited" || rawEmotion === "happy" ? "selected" : ""}>🤩 Excited (រំភើប)</option>
            <option value="terrified" ${rawEmotion === "terrified" || rawEmotion === "fear" ? "selected" : ""}>😨 Terrified (ភ័យខ្លាច)</option>
            <option value="romantic" ${rawEmotion === "romantic" || rawEmotion === "sensual" ? "selected" : ""}>🥰 Romantic (ផ្អែមល្ហែម)</option>
            <option value="suspense" ${rawEmotion === "suspense" || rawEmotion === "mystery" ? "selected" : ""}>🔮 Suspense (អាថ៌កំបាំង)</option>
            <option value="sarcastic" ${rawEmotion === "sarcastic" || rawEmotion === "smirk" ? "selected" : ""}>😏 Sarcastic (បញ្ចើច/ឌឺដង)</option>
            <option value="exhausted" ${rawEmotion === "exhausted" || rawEmotion === "tired" ? "selected" : ""}>😮‍💨 Exhausted (ហត់នឿយ)</option>
          </select>
        </div>
      </td>
      <td class="col-voice">
        <div class="voice-select-wrap">
          <select class="table-select" onchange="onEditSelect(${sub.id}, 'voice', this.value)">
            <option value="Khmer Male 01" ${selectedVoice === "Khmer Male 01" ? "selected" : ""}>👨 Piseth (Male)</option>
            <option value="Khmer Female 01" ${selectedVoice === "Khmer Female 01" ? "selected" : ""}>👩 Sreymom (Female)</option>
            <option value="Khmer Boy 01" ${selectedVoice === "Khmer Boy 01" ? "selected" : ""}>👦 Piseth Boy (ក្មេងប្រុស)</option>
            <option value="Khmer Girl 01" ${selectedVoice === "Khmer Girl 01" ? "selected" : ""}>👧 Sreymom Girl (ក្មេងស្រី)</option>
          </select>
        </div>
      </td>
      <td class="col-status">
        <span class="table-status-pill ${statusClass}" title="Click to cycle status" onclick="cycleSubtitleStatus(${sub.id})">
          ${sub.status || "Ready"}
        </span>
      </td>
      <td class="col-actions">
        <div class="row-actions-wrap">
          <button class="btn-row-action action-play ${isRowPlaying ? 'playing' : ''} ${isRowLoading ? 'loading' : ''}" 
                  id="btn-play-row-${sub.id}"
                  title="Play subtitle audio preview (ស្តាប់សំឡេង)" 
                  onclick="previewSubtitleRow(${sub.id}, event)">
            ${isRowLoading ? `
              <div class="row-audio-spinner"></div>
            ` : isRowPlaying ? `
              <div class="row-wave-visualizer">
                <span class="wave-bar b1"></span>
                <span class="wave-bar b2"></span>
                <span class="wave-bar b3"></span>
                <span class="wave-bar b4"></span>
              </div>
            ` : `
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
            `}
          </button>
          <button class="btn-row-action" title="Regenerate with custom provider/tone" onclick="openRegenerateModal(${sub.id}, event)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
              <path d="M3 3v5h5"/>
              <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/>
              <path d="M21 21v-5h-5"/>
            </svg>
          </button>
          <button class="btn-row-action" title="Duplicate subtitle" onclick="duplicateSubtitleRow(${sub.id}, event)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
          ${_valState.hasIssue ? `<button class="btn-row-action action-fix" title="Auto Fix: clamp overflow / resolve collision" onclick="autoFixTimeline(${sub.id}, event)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>
          </button>` : ''}
          ${sub.syncStatus === 'auto_fixed' ? `<button class="btn-row-action action-undo-fix" title="Undo auto fix — restore original timestamps" onclick="undoTimelineFix(${sub.id}, event)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 14 4 9 9 4"/><path d="M20 20v-7a4 4 0 0 0-4-4H4"/></svg>
          </button>` : ''}
          <button class="btn-row-action action-del" title="Delete subtitle" onclick="deleteSubtitleRow(${sub.id}, event)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
      </td>
    `;

    tr.addEventListener("click", (e) => {
      if (["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(e.target.tagName)) return;
      selectAndSeekSubtitle(sub);
    });

    ui.subtitlesTableBody.appendChild(tr);
  });

  renderPagination(appState.currentPage, totalPages);
  syncSelectAllCheckboxState();
  updateRegenDubButtonCount();
}

window.selectAndSeekSubtitle = function (sub) {
  appState.activeSubtitleId = sub.id;
  seekToTime(sub.start);

  document.querySelectorAll(".subtitles-data-table tbody tr").forEach((tr) => tr.classList.remove("row-active"));
  const row = document.getElementById(`sub-row-${sub.id}`);
  if (row) row.classList.add("row-active");

  document.querySelectorAll(".timeline-block").forEach((b) => b.classList.remove("block-active"));
  const block = document.getElementById(`time-block-${sub.id}`);
  if (block) block.classList.add("block-active");

  updateVideoSubtitleOverlay(sub.start);
};

window.onEditTimestamp = function (id, field, value) {
  const sub = appState.subtitles.find((s) => s.id === id);
  if (!sub) return;
  const sec = parseTimecode(value);
  if (!isNaN(sec)) {
    sub[field] = Math.max(0, sec);
    // Live-validate after every timestamp edit
    validateAndMarkSubtitle(sub);
    renderTimelineBlocks();
    renderSubtitlesTable();
    showToast(`Updated ${field} to ${value}`);
  }
};

window.onEditText = function (id, field, value) {
  const sub = appState.subtitles.find((s) => s.id === id);
  if (!sub) return;
  sub[field] = value.trim();
  updateVideoSubtitleOverlay(appState.currentTime);
  updateStatusMetrics();
};

window.onEditSelect = function (id, field, value) {
  const sub = appState.subtitles.find((s) => s.id === id);
  if (!sub) return;
  sub[field] = value;

  if (field === "emotion") {
    sub.emotion = value;
    renderSubtitlesTable();
    showToast(`Emotion set to: ${value.toUpperCase()}`);
    return;
  }

  if (field === "speaker") {
    if (value === "Speaker 2" || value.toLowerCase().includes("female")) {
      sub.speaker = "Speaker 2";
      sub.voice = "Khmer Female 01";
    } else if (value.includes("Girl") || value.includes("ស្រី")) {
      sub.speaker = "Speaker 3 (Girl)";
      sub.voice = "Khmer Girl 01";
    } else if (value.includes("Boy") || value.includes("ប្រុស")) {
      sub.speaker = "Speaker 3 (Boy)";
      sub.voice = "Khmer Boy 01";
    } else if (value === "Narrator") {
      sub.speaker = "Narrator";
      sub.voice = "Khmer Male 01";
    } else {
      sub.speaker = "Speaker 1";
      sub.voice = "Khmer Male 01";
    }
  } else if (field === "voice") {
    if (value === "Khmer Female 01") {
      sub.speaker = "Speaker 2";
    } else if (value === "Khmer Girl 01") {
      sub.speaker = "Speaker 3 (Girl)";
    } else if (value === "Khmer Boy 01") {
      sub.speaker = "Speaker 3 (Boy)";
    } else if (value === "Khmer Male 01") {
      if (sub.speaker !== "Narrator") {
        sub.speaker = "Speaker 1";
      }
    }
  }
  renderSubtitlesTable();
  if (typeof renderTimelineBlocks === "function") renderTimelineBlocks();
  showToast(`Updated to ${sub.speaker} (${sub.voice})`);
};

window.cycleSubtitleStatus = function (id) {
  const sub = appState.subtitles.find((s) => s.id === id);
  if (!sub) return;
  if (sub.status === "Ready") sub.status = "Needs Review";
  else if (sub.status === "Needs Review") sub.status = "Translated";
  else sub.status = "Ready";

  renderSubtitlesTable();
  updateStatusMetrics();
};

function getVoiceRateString() {
  const speed = parseFloat(ui.rangeVoiceSpeed ? ui.rangeVoiceSpeed.value : 1.0) || 1.0;
  const pct = Math.round((speed - 1.0) * 100);
  return pct >= 0 ? `+${pct}%` : `${pct}%`;
}

function getVoicePitchString() {
  const pitch = parseInt(ui.rangeVoicePitch ? ui.rangeVoicePitch.value : 0) || 0;
  return pitch >= 0 ? `+${pitch}Hz` : `${pitch}Hz`;
}

window.previewSubtitleRow = async function (id, event) {
  if (event) event.stopPropagation();
  const sub = appState.subtitles.find((s) => s.id === id);
  if (!sub) return;

  // If already playing this row, clicking again will pause/stop
  if (appState.activeAudioRowId === id && appState.previewAudio && !appState.previewAudio.paused) {
    appState.previewAudio.pause();
    appState.activeAudioRowId = null;
    appState.loadingAudioRowId = null;
    renderSubtitlesTable();
    return;
  }

  selectAndSeekSubtitle(sub);

  const textToSay = (sub.khmer_text || sub.text || "").trim();
  if (!textToSay) {
    showToast("No dialogue text to preview");
    return;
  }

  // Resolve voice model and acoustic settings for speaker
  let targetVoice = ui.selectVoiceModel ? ui.selectVoiceModel.value : "km-KH-PisethNeural";
  let targetPitch = getVoicePitchString();
  let targetRate = getVoiceRateString();

  const spk = (sub.speaker || "").toLowerCase();
  const vox = (sub.voice || "").toLowerCase();

  if (vox.includes("female") || spk.includes("speaker 2") || spk.includes("female")) {
    targetVoice = "km-KH-SreymomNeural";
  } else if (vox.includes("girl") || spk.includes("girl")) {
    targetVoice = "km-KH-SreymomNeural";
    targetPitch = "+22Hz";
    targetRate = "+12%";
  } else if (vox.includes("boy") || spk.includes("boy")) {
    targetVoice = "km-KH-PisethNeural";
    targetPitch = "+20Hz";
    targetRate = "+12%";
  } else if (vox.includes("male") || spk.includes("speaker 1")) {
    targetVoice = "km-KH-PisethNeural";
  }

  try {
    appState.loadingAudioRowId = id;
    appState.activeAudioRowId = null;
    renderSubtitlesTable();

    const res = await fetch("/api/tts/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: textToSay,
        voice: targetVoice,
        rate: targetRate,
        pitch: targetPitch,
        emotion: sub.emotion || "neutral",
        pacing: sub.pacing || "normal",
      }),
    });

    if (res.ok) {
      const data = await res.json();
      appState.loadingAudioRowId = null;
      appState.activeAudioRowId = id;
      renderSubtitlesTable();

      appState.previewAudio.src = data.audio_url;

      appState.previewAudio.onended = () => {
        appState.activeAudioRowId = null;
        appState.loadingAudioRowId = null;
        renderSubtitlesTable();
      };
      appState.previewAudio.onpause = () => {
        if (appState.activeAudioRowId === id) {
          appState.activeAudioRowId = null;
          appState.loadingAudioRowId = null;
          renderSubtitlesTable();
        }
      };
      appState.previewAudio.onerror = () => {
        appState.activeAudioRowId = null;
        appState.loadingAudioRowId = null;
        renderSubtitlesTable();
        showToast("Audio playback error");
      };

      await appState.previewAudio.play();
    } else {
      throw new Error(`TTS Preview Status ${res.status}`);
    }
  } catch (e) {
    console.warn("TTS preview fetch error:", e);
    appState.loadingAudioRowId = null;
    appState.activeAudioRowId = null;
    renderSubtitlesTable();
    showToast("Could not preview audio");
  }
};

window.duplicateSubtitleRow = function (id, event) {
  if (event) event.stopPropagation();
  const idx = appState.subtitles.findIndex((s) => s.id === id);
  if (idx === -1) return;
  const original = appState.subtitles[idx];
  const newSub = {
    ...original,
    id: Date.now(),
    start: original.end,
    end: original.end + Math.max(1, original.end - original.start),
    text: `${original.text || ''}`,
    khmer_text: `${original.khmer_text || ''}`,
    status: "Needs Review",
  };
  appState.subtitles.splice(idx + 1, 0, newSub);
  renderSubtitlesTable();
  renderTimelineBlocks();
  updateStatusMetrics();
  showToast("Subtitle row duplicated");
};

window.deleteSubtitleRow = function (id, event) {
  if (event) event.stopPropagation();
  appState.subtitles = appState.subtitles.filter((s) => s.id !== id);
  renderSubtitlesTable();
  renderTimelineBlocks();
  updateStatusMetrics();
  showToast("Subtitle row deleted");
};

// ==========================================================================
// 4. Subtitle Editing Features Toolbar Actions
// ==========================================================================
function addNewSubtitleSegment() {
  const current = appState.currentTime;
  const newSub = {
    id: Date.now(),
    start: parseFloat(current.toFixed(1)),
    end: parseFloat((current + 3.0).toFixed(1)),
    text: "New dialogue segment...",
    khmer_text: "",
    speaker: "Speaker 1",
    voice: ui.selectVoiceModel.value.includes("Sreymom") ? "Khmer Female 01" : "Khmer Male 01",
    status: "Needs Review",
  };
  appState.subtitles.push(newSub);
  appState.subtitles = sanitizeSubtitleTimelines(appState.subtitles, 0.25);
  renderSubtitlesTable();
  renderTimelineBlocks();
  updateStatusMetrics();
  selectAndSeekSubtitle(newSub);
  showToast("Added new subtitle segment");
}

async function triggerAutoTranscription() {
  if (!appState.sessionId) {
    showToast("Please upload a video or audio file first.");
    ui.hiddenVideoUpload.click();
    return;
  }

  showToast("Transcribing speech with AI...");
  updateProjectStatus("Processing");
  showPlayerLoading("Running Speech-to-Text (STT)...");
  ui.pipelineProgressFill.style.width = "25%";
  ui.progressPctText.textContent = "25%";
  ui.pipelineStepCaption.textContent = "Transcribing audio with speech models...";

  try {
    const selectedEngine = (ui.selectSttEngine && ui.selectSttEngine.value) || "whisper";
    const selectedModel = (ui.selectSttModel && ui.selectSttModel.value) || "small";
    const sourceLang = (ui.selectSourceLang && ui.selectSourceLang.value) || "auto";
    const selectedVoice = (ui.selectVoiceModel && ui.selectVoiceModel.value) || "auto";

    const res = await fetch("/api/stt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: appState.sessionId,
        engine: selectedEngine,
        model_name: selectedModel,
        language: sourceLang,
        voice: selectedVoice,
        api_key: localStorage.getItem("khmerdub_gemini_api_key") || null,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "STT failed");
    }

    const data = await res.json();
    const rawSegments = data.segments || [];

    const mapped = rawSegments.map((seg, idx) => {
      const spk = seg.speaker || "Speaker 1";
      let defaultVoice = "Khmer Male 01";
      if (spk === "Speaker 2" || spk.toLowerCase().includes("female")) {
        defaultVoice = "Khmer Female 01";
      } else if (spk.includes("Girl") || spk.includes("ស្រី")) {
        defaultVoice = "Khmer Girl 01";
      } else if (spk.includes("Boy") || spk.includes("ប្រុស")) {
        defaultVoice = "Khmer Boy 01";
      }
      const voice = seg.voice || defaultVoice;
      const emotion = seg.emotion || "neutral";
      return {
        id: seg.id || idx + 1,
        start: parseFloat(seg.start || 0),
        end: parseFloat(seg.end || 0),
        text: seg.text || "",
        khmer_text: seg.khmer_text || "",
        speaker: spk,
        voice: voice,
        emotion: emotion,
        status: seg.khmer_text ? "Ready" : "Needs Review",
      };
    });
    const mergedSegments = smartMergeDialogueFragments(mapped);
    const maxDur = (appState.duration && appState.duration > 0) ? appState.duration : (data.media_info?.duration || null);
    appState.subtitles = sanitizeSubtitleTimelines(mergedSegments, 0.05, maxDur);

    ui.pipelineProgressFill.style.width = "50%";
    ui.progressPctText.textContent = "50%";
    ui.pipelineStepCaption.textContent = `Transcribed ${appState.subtitles.length} dialogue segments.`;

    renderSubtitlesTable();
    renderTimelineBlocks();
    updateStatusMetrics();
    updateProjectStatus("Draft");
    showToast(`Transcribed ${appState.subtitles.length} subtitle segments!`);

    // Auto translate if checked
    if (ui.chkAutoTranslate.checked) {
      translateAllSubtitles();
    }

  } catch (err) {
    console.error("STT error:", err);
    showToast(`Transcription error: ${err.message}`);
    updateProjectStatus("Draft");
  } finally {
    hidePlayerLoading();
  }
}

// AI Storytelling Recap (សម្រាយរឿងតាម Timestamps និង Auto Text ចូល Subtitle Table)
async function triggerAiStoryRecap() {
  if (!appState.sessionId) {
    showToast("សូម Upload វីដេអូ ឬ Audio ជាមុនសិន!");
    if (ui.hiddenVideoUpload) ui.hiddenVideoUpload.click();
    return;
  }

  // Visual button loading state
  if (ui.btnAutoStoryRecap) {
    ui.btnAutoStoryRecap.classList.add("loading-recap");
  }
  if (ui.labelAutoStoryRecap) {
    ui.labelAutoStoryRecap.textContent = "កំពុងសម្រាយរឿង...";
  }
  if (ui.tbBtnStoryRecap) {
    ui.tbBtnStoryRecap.classList.add("loading-recap");
  }

  showToast("✨ កំពុងបម្លែងសាច់រឿងសម្រាយតាម Timestamps របស់វីដេអូ...");
  updateProjectStatus("Processing");
  showPlayerLoading("កំពុងបម្លែងសាច់រឿងសម្រាយតាម Timestamps ជាមួយ AI...");
  if (ui.pipelineProgressFill) ui.pipelineProgressFill.style.width = "40%";
  if (ui.progressPctText) ui.progressPctText.textContent = "40%";
  if (ui.pipelineStepCaption) ui.pipelineStepCaption.textContent = "Generating Khmer third-person movie recap narrative...";

  try {
    const apiKey = localStorage.getItem("khmerdub_gemini_api_key") || null;
    const res = await fetch("/api/recap/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: appState.sessionId,
        segments: appState.subtitles && appState.subtitles.length > 0 ? appState.subtitles : null,
        total_duration: appState.duration || (ui.mainVideoPlayer ? ui.mainVideoPlayer.duration : 30.0),
        style: (appState.recapStudio && appState.recapStudio.activeStyle) || "suspense",
        include_hook: (appState.recapStudio && appState.recapStudio.includeHook) ?? true,
        include_cta: (appState.recapStudio && appState.recapStudio.includeCta) ?? true,
        hybrid_dialogue: (appState.recapStudio && appState.recapStudio.hybridDialogue) !== false,
        narrator_voice: (appState.recapStudio && appState.recapStudio.voice) || "km-KH-PisethNeural",
        pacing: (appState.recapStudio && appState.recapStudio.pacing) || "normal",
        model_name: (appState.recapStudio && appState.recapStudio.modelName) || "gemini-3.5-flash",
        api_key: apiKey,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Recap generation failed");
    }

    const data = await res.json();
    const recapSegments = data.segments || [];

    if (recapSegments.length > 0) {
      pushSubtitleHistory("AI Story Recap");
      const mapped = recapSegments.map((s, idx) => ({
        id: s.id || idx + 1,
        start: parseFloat(s.start || 0),
        end: parseFloat(s.end || 0),
        text: s.text || `Scene #${idx + 1}`,
        khmer_text: s.khmer_text || "",
        speaker: s.speaker || "Narrator",
        voice: s.voice || "km-KH-PisethNeural",
        status: s.status || "Ready",
        tag: s.tag || "story",
      }));
      appState.subtitles = sanitizeSubtitleTimelines(mapped, 0.35, appState.duration);

      // Render updated subtitle data table directly
      renderSubtitlesTable();
      renderTimelineBlocks();
      updateStatusMetrics();
      updateVideoSubtitleOverlay(appState.currentTime);

      // Select first segment and seek
      if (appState.subtitles.length > 0) {
        selectAndSeekSubtitle(appState.subtitles[0]);
      }

      // Switch to Story Recap Studio Tab to view narrator voice & BGM settings
      if (typeof switchStudioTab === "function") {
        switchStudioTab("recap");
      }

      updateProjectStatus("Draft");
      showToast(`🎉 បានសម្រាយរឿង និងបញ្ចូលក្នុងតារាង Subtitles ដោយស្វ័យប្រវត្តិចំនួន ${appState.subtitles.length} វគ្គ!`);
    } else {
      showToast("មិនទទួលបានទិន្នន័យអត្ថបទសម្រាយរឿងទេ");
    }
  } catch (err) {
    console.error("AI Story Recap error:", err);
    showToast(`កំហុសសម្រាយរឿង៖ ${err.message}`);
    updateProjectStatus("Draft");
  } finally {
    if (ui.btnAutoStoryRecap) {
      ui.btnAutoStoryRecap.classList.remove("loading-recap");
    }
    if (ui.labelAutoStoryRecap) {
      ui.labelAutoStoryRecap.textContent = "AI Story Recap (សម្រាយរឿង)";
    }
    if (ui.tbBtnStoryRecap) {
      ui.tbBtnStoryRecap.classList.remove("loading-recap");
    }
    hidePlayerLoading();
  }
}

// ==========================================================================
// 4. Multi-Provider Translation Engine & AI Settings
// ==========================================================================

function bindTranslationEngineEvents() {
  if (ui.btnAiSettingsTrigger) {
    ui.btnAiSettingsTrigger.addEventListener("click", () => openAiSettingsModal("engine"));
  }
  if (ui.btnQuickConfigEngine) {
    ui.btnQuickConfigEngine.addEventListener("click", () => openAiSettingsModal("engine"));
  }
  if (ui.btnCloseAiSettingsModal) {
    ui.btnCloseAiSettingsModal.addEventListener("click", closeAiSettingsModal);
  }
  if (ui.btnCancelAiSettings) {
    ui.btnCancelAiSettings.addEventListener("click", closeAiSettingsModal);
  }
  if (ui.btnSaveAiSettings) {
    ui.btnSaveAiSettings.addEventListener("click", saveAiSettings);
  }
  if (ui.modalAiSettings) {
    ui.modalAiSettings.addEventListener("click", (e) => {
      if (e.target === ui.modalAiSettings) closeAiSettingsModal();
    });
  }

  // Tabs
  if (ui.tabGeneralTrigger) {
    ui.tabGeneralTrigger.addEventListener("click", () => switchAiSettingsTab("general"));
  }
  if (ui.tabEngineTrigger) {
    ui.tabEngineTrigger.addEventListener("click", () => switchAiSettingsTab("engine"));
  }
  if (ui.tabGlossaryTrigger) {
    ui.tabGlossaryTrigger.addEventListener("click", () => switchAiSettingsTab("glossary"));
  }
  if (ui.tabMemoryTrigger) {
    ui.tabMemoryTrigger.addEventListener("click", () => switchAiSettingsTab("memory"));
  }
  if (ui.tabMonitoringTrigger) {
    ui.tabMonitoringTrigger.addEventListener("click", () => switchAiSettingsTab("monitoring"));
  }
  if (ui.tabUpdatesTrigger) {
    ui.tabUpdatesTrigger.addEventListener("click", () => switchAiSettingsTab("updates"));
  }

  // Application update actions
  const btnCheckUpdate = document.getElementById("btnCheckUpdate");
  if (btnCheckUpdate) btnCheckUpdate.addEventListener("click", () => checkForAppUpdate(true));
  const btnInstallUpdate = document.getElementById("btnInstallUpdate");
  if (btnInstallUpdate) btnInstallUpdate.addEventListener("click", installAppUpdate);
  const btnCancelUpdate = document.getElementById("btnCancelUpdate");
  if (btnCancelUpdate) btnCancelUpdate.addEventListener("click", cancelAppUpdate);
  const btnSaveUpdateSource = document.getElementById("btnSaveUpdateSource");
  if (btnSaveUpdateSource) btnSaveUpdateSource.addEventListener("click", saveUpdateSource);

  // Radio selection for translation engine
  document.querySelectorAll("input[name='translationEngineRadio']").forEach((radio) => {
    radio.addEventListener("change", (e) => onEngineRadioChange(e.target.value));
  });

  // Clicking on provider card body selects radio
  document.querySelectorAll(".provider-card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (["INPUT", "SELECT", "BUTTON"].includes(e.target.tagName)) return;
      const r = card.querySelector("input[type='radio']");
      if (r) {
        r.checked = true;
        onEngineRadioChange(r.value);
      }
    });
  });

  // Sync model changes inside provider cards
  if (ui.selectGeminiEngineModel) {
    ui.selectGeminiEngineModel.addEventListener("change", (e) => {
      if (appState.translationEngine.activeProvider === "gemini") {
        appState.translationEngine.activeModel = e.target.value;
        if (ui.selectProjectModel) ui.selectProjectModel.value = e.target.value;
      }
    });
  }
  if (ui.selectOpenAIEngineModel) {
    ui.selectOpenAIEngineModel.addEventListener("change", (e) => {
      if (appState.translationEngine.activeProvider === "openai") {
        appState.translationEngine.activeModel = e.target.value;
        if (ui.selectProjectModel) ui.selectProjectModel.value = e.target.value;
      }
    });
  }
  if (ui.selectGoogleEngineModel) {
    ui.selectGoogleEngineModel.addEventListener("change", (e) => {
      if (appState.translationEngine.activeProvider === "google_cloud") {
        appState.translationEngine.activeModel = e.target.value;
        if (ui.selectProjectModel) ui.selectProjectModel.value = e.target.value;
      }
    });
  }
  if (ui.inputLocalModelName) {
    ui.inputLocalModelName.addEventListener("input", (e) => {
      if (appState.translationEngine.activeProvider === "local_model") {
        appState.translationEngine.activeModel = e.target.value.trim();
        if (ui.selectProjectModel) ui.selectProjectModel.value = e.target.value.trim();
      }
    });
  }

  // Live status badge updates when typing API keys or endpoints
  [ui.inputGeminiCustomKey, ui.inputCodeCraftCustomKey, ui.inputCodeCraftBaseUrl, ui.inputOpenAICustomKey, ui.inputGoogleCustomKey, ui.inputLocalEndpoint].forEach((inp) => {
    if (inp) {
      inp.addEventListener("input", () => updateAllProviderStatusBadges());
    }
  });

  // Project Translation Sidebar
  if (ui.selectProjectProvider) {
    ui.selectProjectProvider.addEventListener("change", (e) => onProjectProviderChange(e.target.value));
  }
  if (ui.selectProjectModel) {
    ui.selectProjectModel.addEventListener("change", (e) => {
      appState.translationEngine.activeModel = e.target.value;
      const prov = appState.translationEngine.activeProvider;
      if (prov === "gemini" && ui.selectGeminiEngineModel) ui.selectGeminiEngineModel.value = e.target.value;
      if (prov === "openai" && ui.selectOpenAIEngineModel) ui.selectOpenAIEngineModel.value = e.target.value;
      if (prov === "google_cloud" && ui.selectGoogleEngineModel) ui.selectGoogleEngineModel.value = e.target.value;
      if (prov === "local_model" && ui.inputLocalModelName) ui.inputLocalModelName.value = e.target.value;
    });
  }
  if (ui.btnTranslateSubtitlesProject) {
    ui.btnTranslateSubtitlesProject.addEventListener("click", startProjectSubtitleTranslation);
  }
  if (ui.btnCancelTranslation) {
    ui.btnCancelTranslation.addEventListener("click", cancelProjectSubtitleTranslation);
  }

  // Glossary
  if (ui.btnAddGlossaryTerm) {
    ui.btnAddGlossaryTerm.addEventListener("click", addGlossaryTermHandler);
  }
  if (ui.inputGlossaryTarget) {
    ui.inputGlossaryTarget.addEventListener("keydown", (e) => {
      if (e.key === "Enter") addGlossaryTermHandler();
    });
  }

  // Translation Memory
  if (ui.btnRefreshTM) {
    ui.btnRefreshTM.addEventListener("click", loadTranslationMemory);
  }

  // Monitoring
  if (ui.btnRefreshStats) {
    ui.btnRefreshStats.addEventListener("click", loadAdminStats);
  }

  // Single Segment Regenerate Modal
  if (ui.btnCloseRegenerateModal) {
    ui.btnCloseRegenerateModal.addEventListener("click", closeRegenerateModal);
  }
  if (ui.btnCancelRegen) {
    ui.btnCancelRegen.addEventListener("click", closeRegenerateModal);
  }
  if (ui.btnDoRegenerate) {
    ui.btnDoRegenerate.addEventListener("click", doRegenerateSegment);
  }
  if (ui.btnApplyRegen) {
    ui.btnApplyRegen.addEventListener("click", applyRegenerateToSubtitle);
  }
  if (ui.modalRegenerateSegment) {
    ui.modalRegenerateSegment.addEventListener("click", (e) => {
      if (e.target === ui.modalRegenerateSegment) closeRegenerateModal();
    });
  }
}

function updateAllProviderStatusBadges(opts = {}) {
  const badgeGemini = document.getElementById("badgeGeminiStatus");
  const badgeCodeCraft = document.getElementById("badgeCodeCraftStatus");
  const badgeOpenAI = document.getElementById("badgeOpenAIStatus");
  const badgeGoogle = document.getElementById("badgeGoogleStatus");
  const badgeLocal = document.getElementById("badgeLocalStatus");

  const geminiKey = opts.geminiKey ?? (ui.inputGeminiCustomKey?.value.trim() || appState.geminiApiKey || localStorage.getItem("khmerdub_gemini_api_key") || (appState.hasServerApiKey ? "server_key" : ""));
  if (badgeGemini) {
    if (geminiKey) {
      badgeGemini.className = "provider-status-badge status-connected";
      badgeGemini.innerHTML = `<span class="status-dot"></span> Connected`;
    } else {
      badgeGemini.className = "provider-status-badge status-unconfigured";
      badgeGemini.innerHTML = `<span class="status-dot"></span> Not configured`;
    }
  }

  const codecraftKey = opts.codecraftKey ?? (ui.inputCodeCraftCustomKey?.value.trim() || localStorage.getItem("khmerdub_codecraft_api_key") || "");
  if (badgeCodeCraft) {
    if (codecraftKey) {
      badgeCodeCraft.className = "provider-status-badge status-connected";
      badgeCodeCraft.innerHTML = `<span class="status-dot"></span> Ready / Key set`;
    } else {
      badgeCodeCraft.className = "provider-status-badge status-unconfigured";
      badgeCodeCraft.innerHTML = `<span class="status-dot"></span> Not configured`;
    }
  }

  const openaiKey = opts.openaiKey ?? (ui.inputOpenAICustomKey?.value.trim() || localStorage.getItem("khmerdub_openai_api_key") || "");
  if (badgeOpenAI) {
    if (openaiKey) {
      badgeOpenAI.className = "provider-status-badge status-connected";
      badgeOpenAI.innerHTML = `<span class="status-dot"></span> Ready / Key set`;
    } else {
      badgeOpenAI.className = "provider-status-badge status-unconfigured";
      badgeOpenAI.innerHTML = `<span class="status-dot"></span> Not configured`;
    }
  }

  const googleKey = opts.googleKey ?? (ui.inputGoogleCustomKey?.value.trim() || localStorage.getItem("khmerdub_google_api_key") || "");
  if (badgeGoogle) {
    if (googleKey) {
      badgeGoogle.className = "provider-status-badge status-connected";
      badgeGoogle.innerHTML = `<span class="status-dot"></span> Ready / Key set`;
    } else {
      badgeGoogle.className = "provider-status-badge status-unconfigured";
      badgeGoogle.innerHTML = `<span class="status-dot"></span> Not configured`;
    }
  }

  const localEndpoint = opts.localEndpoint ?? (ui.inputLocalEndpoint?.value.trim() || "");
  if (badgeLocal) {
    if (localEndpoint) {
      badgeLocal.className = "provider-status-badge status-connected";
      badgeLocal.innerHTML = `<span class="status-dot"></span> Configured`;
    } else {
      badgeLocal.className = "provider-status-badge status-unconfigured";
      badgeLocal.innerHTML = `<span class="status-dot"></span> Not configured`;
    }
  }
}

function openAiSettingsModal(tabName = "engine") {
  if (!ui.modalAiSettings) return;
  ui.modalAiSettings.classList.remove("hidden");
  switchAiSettingsTab(tabName);

  // Restore local cache immediately so modal is instantly populated
  const savedAi = localStorage.getItem("khmerdub_ai_settings");
  if (savedAi) {
    try {
      applyAiSettingsToUI(JSON.parse(savedAi));
    } catch (e) { }
  }
  updateAllProviderStatusBadges();

  // Then fetch latest settings from backend
  fetchAiSettings();
}

function closeAiSettingsModal() {
  const modal = ui.modalAiSettings || document.getElementById("modalAiSettings");
  if (modal) modal.classList.add("hidden");
}
window.closeAiSettingsModal = closeAiSettingsModal;
window.openAiSettingsModal = openAiSettingsModal;

// ==========================================================================
// General Settings — Save / Load (localStorage)
// ==========================================================================
const GENERAL_SETTINGS_KEY = "khmerdub_general_settings";

function saveGeneralSettings() {
  const settings = {
    canvasAspect: (document.getElementById("selectCanvasAspect") || {}).value || "original",
    blurEnabled: !!(document.getElementById("chkBlurSubtitles") || {}).checked,
    autoTranscribe: !!(document.getElementById("chkAutoTranscribe") || {}).checked,
    autoTranslate: !!(document.getElementById("chkAutoTranslate") || {}).checked,
    voiceSync: !!(document.getElementById("chkVoiceSync") || {}).checked,
    noiseReduction: !!(document.getElementById("chkNoiseReduction") || {}).checked,
    khmerSpell: !!(document.getElementById("chkKhmerSpell") || {}).checked,
    preserveBGM: !!(document.getElementById("chkPreserveBGM") || {}).checked,
    vocalRemovalMethod: (document.getElementById("selVocalRemovalMethod") || {}).value || "ai_bs_roformer",
  };
  localStorage.setItem(GENERAL_SETTINGS_KEY, JSON.stringify(settings));
  // Sync canvas aspect to appState
  if (settings.canvasAspect && typeof updateCanvasAspect === "function") {
    updateCanvasAspect(settings.canvasAspect);
  }
  if (appState.blurStudio) appState.blurStudio.enabled = settings.blurEnabled;
  showToast("✅ Settings saved");
}

function loadGeneralSettings() {
  try {
    const raw = localStorage.getItem(GENERAL_SETTINGS_KEY);
    if (!raw) return;
    let s;
    try { s = JSON.parse(raw); } catch (e) { return; }
    const setChk = (id, val) => { const el = document.getElementById(id); if (el) el.checked = val; };
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    if (s.canvasAspect !== undefined) setVal("selectCanvasAspect", s.canvasAspect);
    if (s.blurEnabled !== undefined) setChk("chkEnableBlurExport", s.blurEnabled);
    if (s.autoTranscribe !== undefined) setChk("chkAutoTranscribe", s.autoTranscribe);
    if (s.autoTranslate !== undefined) setChk("chkAutoTranslate", s.autoTranslate);
    if (s.voiceSync !== undefined) setChk("chkVoiceSync", s.voiceSync);
    if (s.noiseReduction !== undefined) setChk("chkNoiseReduction", s.noiseReduction);
    if (s.khmerSpell !== undefined) setChk("chkKhmerSpell", s.khmerSpell);
    if (s.preserveBGM !== undefined) setChk("chkPreserveBGM", s.preserveBGM);
    if (s.vocalRemovalMethod !== undefined) setVal("selVocalRemovalMethod", s.vocalRemovalMethod);
  } catch (e) { console.warn("loadGeneralSettings error:", e); }
}

function bindGeneralSettingsAutoSave() {
  try {
    const ids = ["chkEnableBlurExport", "chkAutoTranscribe", "chkAutoTranslate",
                 "chkVoiceSync", "chkNoiseReduction", "chkKhmerSpell", "chkPreserveBGM"];
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", saveGeneralSettings);
    });
    const aspect = document.getElementById("selectCanvasAspect");
    if (aspect) aspect.addEventListener("change", saveGeneralSettings);
    const methodEl = document.getElementById("selVocalRemovalMethod");
    if (methodEl) methodEl.addEventListener("change", saveGeneralSettings);
  } catch (e) { console.warn("bindGeneralSettingsAutoSave error:", e); }
}
window.saveGeneralSettings = saveGeneralSettings;


function switchAiSettingsTab(tabName) {
  const tabs = [
    { name: "general", btn: ui.tabGeneralTrigger, panel: ui.panelGeneral },
    { name: "engine", btn: ui.tabEngineTrigger, panel: ui.panelTranslationEngine },
    { name: "glossary", btn: ui.tabGlossaryTrigger, panel: ui.panelGlossary },
    { name: "memory", btn: ui.tabMemoryTrigger, panel: ui.panelMemory },
    { name: "monitoring", btn: ui.tabMonitoringTrigger, panel: ui.panelMonitoring },
    { name: "updates", btn: ui.tabUpdatesTrigger, panel: ui.panelUpdates },
  ];

  tabs.forEach((t) => {
    if (t.btn) t.btn.classList.toggle("active", t.name === tabName);
    if (t.panel) {
      if (t.name === tabName) {
        t.panel.classList.remove("hidden");
        t.panel.classList.add("active-tab-panel");
      } else {
        t.panel.classList.add("hidden");
        t.panel.classList.remove("active-tab-panel");
      }
    }
  });

  if (tabName === "general") loadGeneralSettings();
  if (tabName === "glossary") loadGlossary();
  if (tabName === "memory") loadTranslationMemory();
  if (tabName === "monitoring") loadAdminStats();
  if (tabName === "updates") loadUpdatePanel();
}

// ==========================================================================
// Application Updates (Settings -> Updates)
// ==========================================================================
const appUpdateState = {
  status: null,
  targetVersion: "",
  pollTimer: null,
  installing: false,
  checking: false,
};

function updateEl(id) {
  return document.getElementById(id);
}

function setUpdateStatusText(text) {
  const el = updateEl("updateStatusText");
  if (el) el.textContent = text;
}

function setUpdateProgress(percent, label) {
  const wrap = updateEl("updateProgressWrap");
  const fill = updateEl("updateProgressFill");
  const text = updateEl("updateProgressLabel");
  if (!wrap) return;
  if (percent === null) {
    wrap.classList.add("hidden");
    return;
  }
  const safe = Math.max(0, Math.min(100, Number(percent) || 0));
  wrap.classList.remove("hidden");
  if (fill) fill.style.width = safe + "%";
  if (text) text.textContent = label || safe + "%";
}

function setUpdateButtons({ check, install, cancel, checkDisabled }) {
  const checkBtn = updateEl("btnCheckUpdate");
  const installBtn = updateEl("btnInstallUpdate");
  const cancelBtn = updateEl("btnCancelUpdate");
  if (checkBtn) {
    checkBtn.classList.toggle("hidden", check === false);
    checkBtn.disabled = !!checkDisabled;
  }
  if (installBtn) installBtn.classList.toggle("hidden", !install);
  if (cancelBtn) cancelBtn.classList.toggle("hidden", !cancel);
}

function renderUpdateStatus(data) {
  if (!data) return;
  appUpdateState.status = data;

  const versionBadge = updateEl("updateCurrentVersion");
  if (versionBadge) versionBadge.textContent = "Version " + (data.current_version || "—");

  const srcInput = updateEl("inputUpdateSource");
  if (srcInput && document.activeElement !== srcInput && data.source) {
    srcInput.value = data.source;
  }

  const hint = updateEl("updateSourceHint");
  const notes = updateEl("updateNotes");
  const newBadge = updateEl("updateNewBadge");
  const busyStates = ["downloading", "verifying", "extracting", "restarting"];
  const busy = busyStates.includes(data.state);

  if (newBadge) newBadge.classList.toggle("hidden", !data.available || busy);

  if (notes) {
    if (data.available && data.notes) {
      notes.textContent = "What's new:\n" + data.notes;
      notes.classList.remove("hidden");
    } else {
      notes.classList.add("hidden");
    }
  }

  if (hint) {
    if (data.install_reason && !data.can_install) {
      hint.textContent = data.install_reason;
    } else if (data.configured && data.source) {
      hint.textContent = "Update source: " + data.source;
    } else {
      hint.textContent = "No update source configured yet.";
    }
  }

  if (data.state === "error") {
    setUpdateStatusText("Update failed: " + (data.error || "unknown error"));
  } else if (busy) {
    setUpdateStatusText(data.message || "Updating...");
  } else if (data.error) {
    setUpdateStatusText(data.error);
  } else if (!data.configured) {
    setUpdateStatusText("Updates are not configured yet. The administrator must set the release source below.");
  } else if (data.available) {
    const size = data.size_human ? ` Download size: ~${data.size_human}.` : "";
    setUpdateStatusText(
      `Version ${data.latest_version} is available (you have ${data.current_version}).${size}`
    );
  } else if (data.latest_version) {
    setUpdateStatusText(`You are using the latest version (${data.current_version}).`);
  } else {
    setUpdateStatusText('Click "Check for Updates" to see if a newer version is available.');
  }

  if (busy) {
    setUpdateProgress(data.progress || 0, (data.progress || 0) + "%");
  } else if (data.available) {
    setUpdateProgress(null);
  } else {
    setUpdateProgress(null);
  }

  const canInstall = !!(data.available && data.can_install && !busy);
  setUpdateButtons({
    check: !busy,
    install: canInstall,
    cancel: busy && data.state !== "restarting",
    checkDisabled: busy,
  });

  if (busy && data.state !== "restarting" && !appUpdateState.pollTimer) {
    startUpdatePolling();
  }
}

async function loadUpdateStatus() {
  try {
    const res = await fetch("/api/update/status", { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    return null;
  }
}

async function loadUpdatePanel() {
  const data = await loadUpdateStatus();
  if (!data) {
    setUpdateStatusText("Could not read the update status. Is the local server running?");
    return;
  }
  renderUpdateStatus(data);
  if (data.configured && !data.latest_version && !["downloading", "verifying", "extracting", "restarting"].includes(data.state)) {
    checkForAppUpdate(false);
  }
}

async function checkForAppUpdate(userInitiated) {
  if (appUpdateState.checking) return;
  appUpdateState.checking = true;
  const checkBtn = updateEl("btnCheckUpdate");
  if (checkBtn) checkBtn.disabled = true;
  if (userInitiated) setUpdateStatusText("Checking for updates...");
  try {
    const res = await fetch("/api/update/check", { method: "POST", cache: "no-store" });
    const data = await res.json();
    renderUpdateStatus(data);
    if (userInitiated) {
      if (data.error) showToast("Update check failed: " + data.error);
      else if (!data.configured) showToast("Update source is not configured.");
      else if (data.available) showToast(`New version ${data.latest_version} is available.`);
      else showToast("You are using the latest version.");
    }
  } catch (err) {
    if (userInitiated) showToast("Update check failed: " + err.message);
  } finally {
    appUpdateState.checking = false;
    if (checkBtn) checkBtn.disabled = false;
  }
}

async function installAppUpdate() {
  if (appUpdateState.installing) return;
  appUpdateState.installing = true;
  const status = appUpdateState.status || {};
  appUpdateState.targetVersion = status.latest_version || "";
  setUpdateButtons({ check: false, install: false, cancel: true });
  setUpdateStatusText("Starting download...");
  setUpdateProgress(1, "1%");
  try {
    const res = await fetch("/api/update/install", { method: "POST", cache: "no-store" });
    const data = await res.json();
    if (!data.success) {
      appUpdateState.installing = false;
      setUpdateButtons({ check: true, install: !!(status.available && status.can_install), cancel: false });
      setUpdateStatusText(data.error || "Update could not be started.");
      showToast(data.error || "Update could not be started.");
      return;
    }
    if (data.target_version) appUpdateState.targetVersion = data.target_version;
    startUpdatePolling();
  } catch (err) {
    appUpdateState.installing = false;
    setUpdateButtons({ check: true, install: !!(status.available && status.can_install), cancel: false });
    setUpdateStatusText("Update could not be started: " + err.message);
  }
}

async function cancelAppUpdate() {
  try {
    await fetch("/api/update/cancel", { method: "POST", cache: "no-store" });
    const data = await loadUpdateStatus();
    if (data) renderUpdateStatus(data);
    showToast("Update cancelled.");
  } catch (err) {
    showToast("Could not cancel the update.");
  }
}

async function saveUpdateSource() {
  const input = updateEl("inputUpdateSource");
  if (!input) return;
  const source = (input.value || "").trim();
  try {
    const res = await fetch("/api/update/source", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source }),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Could not save the update source.");
      return;
    }
    showToast(source ? "✅ Update source saved" : "Update source cleared");
    checkForAppUpdate(false);
  } catch (err) {
    showToast("Could not save the update source: " + err.message);
  }
}

function startUpdatePolling() {
  if (appUpdateState.pollTimer) return;
  appUpdateState.pollTimer = setInterval(async () => {
    const data = await loadUpdateStatus();
    if (!data) return; // server is restarting
    renderUpdateStatus(data);
    if (data.state === "restarting") {
      stopUpdatePolling();
      waitForAppRestart();
    } else if (data.state === "error") {
      stopUpdatePolling();
      appUpdateState.installing = false;
      setUpdateButtons({
        check: true,
        install: !!(data.available && data.can_install),
        cancel: false,
      });
    } else if (data.state === "idle") {
      stopUpdatePolling();
      appUpdateState.installing = false;
    }
  }, 1500);
}

function stopUpdatePolling() {
  if (appUpdateState.pollTimer) {
    clearInterval(appUpdateState.pollTimer);
    appUpdateState.pollTimer = null;
  }
}

function waitForAppRestart() {
  setUpdateStatusText("Installing the new version and restarting the app. This page will reload automatically...");
  setUpdateProgress(100, "100%");
  setUpdateButtons({ check: false, install: false, cancel: false });

  let attempts = 0;
  let sawGap = false;
  const timer = setInterval(async () => {
    attempts += 1;
    try {
      const res = await fetch("/health?t=" + Date.now(), { cache: "no-store" });
      if (res.ok) {
        const health = await res.json();
        const match = !appUpdateState.targetVersion || health.version === appUpdateState.targetVersion;
        if (sawGap || match) {
          clearInterval(timer);
          location.reload();
          return;
        }
      }
    } catch (err) {
      sawGap = true;
    }
    if (attempts >= 180) {
      clearInterval(timer);
      setUpdateStatusText("The app is taking longer than expected. Close this page and open KhmerDubAI again.");
    }
  }, 2000);
}

function onEngineRadioChange(provider) {
  appState.translationEngine.activeProvider = provider;
  updateProviderCardSelection(provider);

  // Sync with project provider selector in studio sidebar
  if (ui.selectProjectProvider && ui.selectProjectProvider.value !== provider) {
    ui.selectProjectProvider.value = provider;
  }
  onProjectProviderChange(provider);
}

function updateProviderCardSelection(provider) {
  document.querySelectorAll(".provider-card").forEach((c) => {
    const p = c.dataset.provider;
    const r = c.querySelector("input[type='radio']");
    if (p === provider) {
      c.classList.add("active-provider-card");
      if (r) r.checked = true;
    } else {
      c.classList.remove("active-provider-card");
      if (r) r.checked = false;
    }
  });
}

function populateProjectProviderDropdown(providers) {
  if (!ui.selectProjectProvider) return;
  const currentVal = ui.selectProjectProvider.value || appState.translationEngine.activeProvider;
  ui.selectProjectProvider.innerHTML = "";
  providers.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = `${p.name} ${p.id === 'gemini' ? '(Default)' : ''}`.trim();
    if (p.id === currentVal) opt.selected = true;
    ui.selectProjectProvider.appendChild(opt);
  });
  onProjectProviderChange(ui.selectProjectProvider.value, appState.translationEngine.activeModel);
}

function onProjectProviderChange(provider, preferredModel = null) {
  appState.translationEngine.activeProvider = provider;
  if (!ui.selectProjectModel) return;
  ui.selectProjectModel.innerHTML = "";

  const provObj = appState.translationEngine.providers?.find((p) => p.id === provider);
  const models = provObj?.models || [];
  const targetModel = preferredModel || appState.translationEngine.activeModel;

  if (models.length > 0) {
    let matched = false;
    models.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      if (targetModel && m === targetModel) {
        opt.selected = true;
        matched = true;
      } else if (!matched && m === provObj.default_model) {
        opt.selected = true;
      }
      ui.selectProjectModel.appendChild(opt);
    });
  } else {
    const fallbackModels = {
      gemini: ["auto", "gemini-3-flash", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-pro", "gemini-3.6-pro", "gemini-2.5-flash"],
      codecraft: [
        "gemini-3-flash",
        "gemini-3.7-flash",
        "claude-3-5-sonnet-20241022",
        "claude-3-7-sonnet",
        "claude-3-5-haiku-20241022",
        "deepseek-chat",
        "deepseek-reasoner",
        "gpt-4o",
        "gpt-4o-mini",
        "qwen-2.5-coder-32b-instruct"
      ],
      openai: ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
      google_cloud: ["nmt", "base"],
      local_model: ["custom-khmer-model", "vllm-llama", "ollama"],
    };
    const list = fallbackModels[provider] || ["default"];
    let matched = false;
    list.forEach((m, idx) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      if (targetModel && m === targetModel) {
        opt.selected = true;
        matched = true;
      } else if (!matched && idx === 0) {
        opt.selected = true;
      }
      ui.selectProjectModel.appendChild(opt);
    });
  }

  appState.translationEngine.activeModel = ui.selectProjectModel.value;

  // Sync to provider card select
  if (provider === "gemini" && ui.selectGeminiEngineModel) ui.selectGeminiEngineModel.value = appState.translationEngine.activeModel;
  if (provider === "codecraft" && ui.selectCodeCraftEngineModel) ui.selectCodeCraftEngineModel.value = appState.translationEngine.activeModel;
  if (provider === "openai" && ui.selectOpenAIEngineModel) ui.selectOpenAIEngineModel.value = appState.translationEngine.activeModel;
  if (provider === "google_cloud" && ui.selectGoogleEngineModel) ui.selectGoogleEngineModel.value = appState.translationEngine.activeModel;
  if (provider === "local_model" && ui.inputLocalModelName) ui.inputLocalModelName.value = appState.translationEngine.activeModel;
}

function applyAiSettingsToUI(settings) {
  if (!settings) return;
  const prov = settings.provider || settings.translation_provider || "gemini";
  const model = settings.model || settings.translation_model || "gemini-3.5-flash";
  appState.translationEngine.activeProvider = prov;
  appState.translationEngine.activeModel = model;

  updateProviderCardSelection(prov);
  if (ui.selectProjectProvider) {
    ui.selectProjectProvider.value = prov;
  }
  onProjectProviderChange(prov, model);

  if (model) {
    if (prov === "gemini" && ui.selectGeminiEngineModel) ui.selectGeminiEngineModel.value = model;
    if (prov === "codecraft" && ui.selectCodeCraftEngineModel) ui.selectCodeCraftEngineModel.value = model;
    if (prov === "openai" && ui.selectOpenAIEngineModel) ui.selectOpenAIEngineModel.value = model;
    if (prov === "google_cloud" && ui.selectGoogleEngineModel) ui.selectGoogleEngineModel.value = model;
    if (prov === "local_model" && ui.inputLocalModelName) ui.inputLocalModelName.value = model;
  }

  if (settings.options?.provider_models) {
    const pm = settings.options.provider_models;
    if (pm.gemini && ui.selectGeminiEngineModel) ui.selectGeminiEngineModel.value = pm.gemini;
    if (pm.codecraft && ui.selectCodeCraftEngineModel) ui.selectCodeCraftEngineModel.value = pm.codecraft;
    if (pm.openai && ui.selectOpenAIEngineModel) ui.selectOpenAIEngineModel.value = pm.openai;
    if (pm.google_cloud && ui.selectGoogleEngineModel) ui.selectGoogleEngineModel.value = pm.google_cloud;
    if (pm.local_model && ui.inputLocalModelName) ui.inputLocalModelName.value = pm.local_model;
  }

  if (settings.fallback_enabled !== undefined && ui.chkGlobalFallbackEnabled) {
    ui.chkGlobalFallbackEnabled.checked = Boolean(settings.fallback_enabled);
  }
  if (settings.fallback_provider && ui.selectGlobalFallbackProvider) {
    ui.selectGlobalFallbackProvider.value = settings.fallback_provider;
  }

  if (settings.options) {
    if (settings.options.local_endpoint && ui.inputLocalEndpoint) {
      ui.inputLocalEndpoint.value = settings.options.local_endpoint;
    }
    if (settings.options.local_model && ui.inputLocalModelName) {
      ui.inputLocalModelName.value = settings.options.local_model;
    }
    if (settings.options.codecraft_base_url && ui.inputCodeCraftBaseUrl) {
      ui.inputCodeCraftBaseUrl.value = settings.options.codecraft_base_url;
    }
    if (settings.options.style && ui.selectProjectStyle) {
      ui.selectProjectStyle.value = settings.options.style;
    }
    if (settings.options.use_context !== undefined && ui.chkUseContext) {
      ui.chkUseContext.checked = Boolean(settings.options.use_context);
    }
    if (settings.options.preserve_speaker !== undefined && ui.chkPreserveSpeaker) {
      ui.chkPreserveSpeaker.checked = Boolean(settings.options.preserve_speaker);
    }
    if (settings.options.optimize_dubbing !== undefined && ui.chkOptimizeDubbing) {
      ui.chkOptimizeDubbing.checked = Boolean(settings.options.optimize_dubbing);
    }
    if (settings.options.use_translation_memory !== undefined && ui.chkUseTM) {
      ui.chkUseTM.checked = Boolean(settings.options.use_translation_memory);
    }
    if (settings.options.use_glossary !== undefined && ui.chkUseGlossary) {
      ui.chkUseGlossary.checked = Boolean(settings.options.use_glossary);
    }
    if (settings.options.enable_fallback !== undefined && ui.chkEnableFallback) {
      ui.chkEnableFallback.checked = Boolean(settings.options.enable_fallback);
    }
  }

  // Restore credentials to UI inputs & sync localStorage
  const creds = settings.credentials || {};
  const gemKey = creds.gemini_api_key || creds.api_key || localStorage.getItem("khmerdub_gemini_api_key") || "";
  const codecraftKey = creds.codecraft_api_key || localStorage.getItem("khmerdub_codecraft_api_key") || "";
  const codecraftBaseUrl = creds.codecraft_base_url || localStorage.getItem("khmerdub_codecraft_base_url") || "";
  const openKey = creds.openai_api_key || localStorage.getItem("khmerdub_openai_api_key") || "";
  const googleKey = creds.google_api_key || localStorage.getItem("khmerdub_google_api_key") || "";

  if (gemKey) {
    if (ui.inputGeminiCustomKey) ui.inputGeminiCustomKey.value = gemKey;
    if (ui.inputGeminiKey) ui.inputGeminiKey.value = gemKey;
    appState.geminiApiKey = gemKey;
    localStorage.setItem("khmerdub_gemini_api_key", gemKey);
    if (ui.keyIconDot) ui.keyIconDot.classList.add("active");
  }
  if (codecraftKey) {
    if (ui.inputCodeCraftCustomKey) ui.inputCodeCraftCustomKey.value = codecraftKey;
    localStorage.setItem("khmerdub_codecraft_api_key", codecraftKey);
  }
  if (codecraftBaseUrl) {
    if (ui.inputCodeCraftBaseUrl) ui.inputCodeCraftBaseUrl.value = codecraftBaseUrl;
    localStorage.setItem("khmerdub_codecraft_base_url", codecraftBaseUrl);
  }
  if (openKey) {
    if (ui.inputOpenAICustomKey) ui.inputOpenAICustomKey.value = openKey;
    localStorage.setItem("khmerdub_openai_api_key", openKey);
  }
  if (googleKey) {
    if (ui.inputGoogleCustomKey) ui.inputGoogleCustomKey.value = googleKey;
    localStorage.setItem("khmerdub_google_api_key", googleKey);
  }

  updateAllProviderStatusBadges({
    geminiKey: gemKey || (appState.hasServerApiKey ? "server_key" : ""),
    codecraftKey: codecraftKey,
    openaiKey: openKey,
    googleKey: googleKey,
    localEndpoint: ui.inputLocalEndpoint?.value.trim() || "",
  });

  try {
    localStorage.setItem("khmerdub_ai_settings", JSON.stringify(settings));
  } catch (e) { }
}

async function fetchAiSettings() {
  try {
    const res = await fetch("/api/translation/settings");
    if (res.ok) {
      const data = await res.json();
      if (data.settings) {
        applyAiSettingsToUI(data.settings);
      }
    }
  } catch (err) {
    console.warn("Error fetching AI translation settings:", err);
  }
}

async function saveAiSettings() {
  const selectedRadio = document.querySelector("input[name='translationEngineRadio']:checked");
  const provider = selectedRadio ? selectedRadio.value : (appState.translationEngine.activeProvider || "gemini");

  let model = "gemini-3.5-flash";
  if (provider === "gemini" && ui.selectGeminiEngineModel) model = ui.selectGeminiEngineModel.value;
  if (provider === "codecraft" && ui.selectCodeCraftEngineModel) model = ui.selectCodeCraftEngineModel.value;
  if (provider === "openai" && ui.selectOpenAIEngineModel) model = ui.selectOpenAIEngineModel.value;
  if (provider === "google_cloud" && ui.selectGoogleEngineModel) model = ui.selectGoogleEngineModel.value;
  if (provider === "local_model" && ui.inputLocalModelName) model = ui.inputLocalModelName.value.trim();

  const fallbackProvider = ui.selectGlobalFallbackProvider ? ui.selectGlobalFallbackProvider.value : "openai";
  const fallbackEnabled = ui.chkGlobalFallbackEnabled ? ui.chkGlobalFallbackEnabled.checked : true;

  const geminiKey = ui.inputGeminiCustomKey ? ui.inputGeminiCustomKey.value.trim() : "";
  const codecraftKey = ui.inputCodeCraftCustomKey ? ui.inputCodeCraftCustomKey.value.trim() : "";
  const codecraftBaseUrl = ui.inputCodeCraftBaseUrl ? ui.inputCodeCraftBaseUrl.value.trim() : "";
  const openaiKey = ui.inputOpenAICustomKey ? ui.inputOpenAICustomKey.value.trim() : "";
  const googleKey = ui.inputGoogleCustomKey ? ui.inputGoogleCustomKey.value.trim() : "";

  // Retain existing saved keys so leaving input blank NEVER wipes them out!
  const savedGemini = localStorage.getItem("khmerdub_gemini_api_key") || appState.geminiApiKey || "";
  const finalGemini = geminiKey || savedGemini;

  const savedCodecraft = localStorage.getItem("khmerdub_codecraft_api_key") || "";
  const finalCodecraft = codecraftKey || savedCodecraft;

  const savedOpenAI = localStorage.getItem("khmerdub_openai_api_key") || "";
  const finalOpenAI = openaiKey || savedOpenAI;

  const savedGoogle = localStorage.getItem("khmerdub_google_api_key") || "";
  const finalGoogle = googleKey || savedGoogle;

  const credentials = {};
  if (finalGemini) credentials.gemini_api_key = finalGemini;
  if (finalCodecraft) credentials.codecraft_api_key = finalCodecraft;
  if (codecraftBaseUrl || localStorage.getItem("khmerdub_codecraft_base_url")) {
    credentials.codecraft_base_url = codecraftBaseUrl || localStorage.getItem("khmerdub_codecraft_base_url");
  }
  if (finalOpenAI) credentials.openai_api_key = finalOpenAI;
  if (finalGoogle) credentials.google_api_key = finalGoogle;

  // Local storage persistence: NEVER delete keys just because input was left blank!
  if (finalGemini) {
    localStorage.setItem("khmerdub_gemini_api_key", finalGemini);
    appState.geminiApiKey = finalGemini;
    if (ui.inputGeminiKey) ui.inputGeminiKey.value = finalGemini;
    if (ui.inputGeminiCustomKey && !ui.inputGeminiCustomKey.value) ui.inputGeminiCustomKey.value = finalGemini;
    if (ui.keyIconDot) ui.keyIconDot.classList.add("active");
  }

  if (finalCodecraft) {
    localStorage.setItem("khmerdub_codecraft_api_key", finalCodecraft);
  }
  if (codecraftBaseUrl) {
    localStorage.setItem("khmerdub_codecraft_base_url", codecraftBaseUrl);
  }
  if (finalOpenAI) {
    localStorage.setItem("khmerdub_openai_api_key", finalOpenAI);
  }
  if (finalGoogle) {
    localStorage.setItem("khmerdub_google_api_key", finalGoogle);
  }

  const providerModels = {
    gemini: ui.selectGeminiEngineModel?.value || "gemini-3.5-flash",
    codecraft: ui.selectCodeCraftEngineModel?.value || "claude-3-5-sonnet-20241022",
    openai: ui.selectOpenAIEngineModel?.value || "gpt-4o-mini",
    google_cloud: ui.selectGoogleEngineModel?.value || "nmt",
    local_model: ui.inputLocalModelName?.value.trim() || "custom-khmer-model",
  };

  const options = {
    local_endpoint: ui.inputLocalEndpoint?.value.trim() || "http://127.0.0.1:8001",
    local_model: ui.inputLocalModelName?.value.trim() || "custom-khmer-model",
    codecraft_base_url: codecraftBaseUrl || "https://codecraftapi.com/v1",
    provider_models: providerModels,
    style: ui.selectProjectStyle?.value || "natural",
    use_context: ui.chkUseContext ? ui.chkUseContext.checked : true,
    preserve_speaker: ui.chkPreserveSpeaker ? ui.chkPreserveSpeaker.checked : true,
    optimize_dubbing: ui.chkOptimizeDubbing ? ui.chkOptimizeDubbing.checked : true,
    use_translation_memory: ui.chkUseTM ? ui.chkUseTM.checked : true,
    use_glossary: ui.chkUseGlossary ? ui.chkUseGlossary.checked : true,
    enable_fallback: ui.chkEnableFallback ? ui.chkEnableFallback.checked : true,
  };

  const payload = {
    provider,
    model,
    fallback_provider: fallbackProvider,
    fallback_enabled: fallbackEnabled,
    options,
    credentials,
  };

  // Immediate local cache save so UI is instantly persistent even before network finishes
  try {
    localStorage.setItem("khmerdub_ai_settings", JSON.stringify(payload));
  } catch (e) { }

  applyAiSettingsToUI(payload);

  try {
    const res = await fetch("/api/translation/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      if (data.settings) {
        applyAiSettingsToUI(data.settings);
      }
      showToast(`💾 AI Settings saved successfully! (${provider.toUpperCase()})`);
      closeAiSettingsModal();
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(`Failed to save settings to server: ${err.detail || "Server error"}`);
    }
  } catch (e) {
    showToast(`Saved locally! (${provider.toUpperCase()})`);
    closeAiSettingsModal();
  }
}

async function testProvider(provider) {
  const feedbackMap = {
    gemini: { el: document.getElementById("feedbackGemini"), badge: document.getElementById("badgeGeminiStatus") },
    codecraft: { el: document.getElementById("feedbackCodeCraft"), badge: document.getElementById("badgeCodeCraftStatus") },
    openai: { el: document.getElementById("feedbackOpenAI"), badge: document.getElementById("badgeOpenAIStatus") },
    google_cloud: { el: document.getElementById("feedbackGoogle"), badge: document.getElementById("badgeGoogleStatus") },
    local_model: { el: document.getElementById("feedbackLocal"), badge: document.getElementById("badgeLocalStatus") },
  };

  const target = feedbackMap[provider];
  if (target?.el) {
    target.el.textContent = "Testing...";
    target.el.className = "test-result-feedback status-testing";
  }

  const creds = {};
  if (provider === "gemini") {
    const key = ui.inputGeminiCustomKey?.value.trim() || appState.geminiApiKey || localStorage.getItem("khmerdub_gemini_api_key") || "";
    if (key) creds.api_key = key;
  }
  if (provider === "codecraft") {
    const key = ui.inputCodeCraftCustomKey?.value.trim() || localStorage.getItem("khmerdub_codecraft_api_key") || "";
    if (key) creds.api_key = key;
    const baseUrl = ui.inputCodeCraftBaseUrl?.value.trim() || localStorage.getItem("khmerdub_codecraft_base_url") || "";
    if (baseUrl) creds.base_url = baseUrl;
  }
  if (provider === "openai") {
    const key = ui.inputOpenAICustomKey?.value.trim() || localStorage.getItem("khmerdub_openai_api_key") || "";
    if (key) creds.api_key = key;
  }
  if (provider === "google_cloud") {
    const key = ui.inputGoogleCustomKey?.value.trim() || localStorage.getItem("khmerdub_google_api_key") || "";
    if (key) creds.api_key = key;
  }
  if (provider === "local_model") {
    creds.endpoint = ui.inputLocalEndpoint?.value.trim() || "http://127.0.0.1:8001";
    creds.model = ui.inputLocalModelName?.value.trim() || "custom-khmer-model";
  }

  try {
    const res = await fetch("/api/translation/test-provider", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider,
        credentials: Object.keys(creds).length ? creds : null,
      }),
    });

    const data = await res.json();
    if (data.success) {
      if (target?.el) {
        target.el.textContent = `Connected! (${data.latency_ms}ms) Model: ${data.model_tested || 'OK'}`;
        target.el.className = "test-result-feedback status-success";
      }
      if (target?.badge) {
        target.badge.className = "provider-status-badge status-connected";
        target.badge.innerHTML = `<span class="status-dot"></span> Connected`;
      }
      showToast(`${provider.toUpperCase()} connected successfully! (${data.latency_ms}ms)`);
    } else {
      if (target?.el) {
        target.el.textContent = `Error: ${data.message || 'Connection failed'}`;
        target.el.className = "test-result-feedback status-error";
      }
      if (target?.badge) {
        target.badge.className = "provider-status-badge status-unconfigured";
        target.badge.innerHTML = `<span class="status-dot"></span> Failed`;
      }
      showToast(`Connection failed: ${data.message || 'Check credentials'}`);
    }
  } catch (err) {
    if (target?.el) {
      target.el.textContent = `Error: ${err.message}`;
      target.el.className = "test-result-feedback status-error";
    }
    showToast(`Test error: ${err.message}`);
  }
}
window.testProvider = testProvider;

// --- Subtitle Locking ---
function toggleLockSubtitle(id, event) {
  if (event) event.stopPropagation();
  const sub = appState.subtitles.find((s) => s.id === id);
  if (!sub) return;

  sub.locked = !sub.locked;
  renderSubtitlesTable();
  renderTimelineBlocks();
  showToast(`Subtitle #${id} ${sub.locked ? "Locked 🔒 (Protected)" : "Unlocked 🔓"}`);
}
window.toggleLockSubtitle = toggleLockSubtitle;

// --- Subtitle Checkbox Selection & Dub Regeneration ---
function toggleSelectSubtitle(id, isChecked, event) {
  if (event) event.stopPropagation();
  const sub = appState.subtitles.find((s) => s.id === id);
  if (sub) {
    sub.selected = Boolean(isChecked);
  }
  syncSelectAllCheckboxState();
  updateRegenDubButtonCount();
}
window.toggleSelectSubtitle = toggleSelectSubtitle;

function toggleSelectAllSubtitles(isChecked) {
  const filtered = getFilteredSubtitles();
  const targetSubs = filtered.length > 0 ? filtered : appState.subtitles;
  targetSubs.forEach((s) => {
    s.selected = Boolean(isChecked);
  });
  document.querySelectorAll(".sub-row-checkbox").forEach((cb) => {
    const sid = parseInt(cb.getAttribute("data-id"), 10);
    const s = appState.subtitles.find((item) => item.id === sid);
    if (s) cb.checked = Boolean(s.selected);
  });
  syncSelectAllCheckboxState();
  updateRegenDubButtonCount();
}
window.toggleSelectAllSubtitles = toggleSelectAllSubtitles;

function syncSelectAllCheckboxState() {
  const chk = ui.chkSelectAllSubs || document.getElementById("chkSelectAllSubs");
  if (!chk) return;
  const filtered = getFilteredSubtitles();
  const targetSubs = filtered.length > 0 ? filtered : appState.subtitles;
  if (targetSubs.length === 0) {
    chk.checked = false;
    chk.indeterminate = false;
    return;
  }
  const selectedCount = targetSubs.filter((s) => s.selected).length;
  if (selectedCount === targetSubs.length) {
    chk.checked = true;
    chk.indeterminate = false;
  } else if (selectedCount > 0) {
    chk.checked = false;
    chk.indeterminate = true;
  } else {
    chk.checked = false;
    chk.indeterminate = false;
  }
}
window.syncSelectAllCheckboxState = syncSelectAllCheckboxState;

function updateRegenDubButtonCount() {
  const lbl = ui.tbBtnRegenDubLabel || document.getElementById("tbBtnRegenDubLabel");
  if (!lbl) return;
  const selectedCount = appState.subtitles.filter((s) => s.selected).length;
  if (selectedCount > 0) {
    lbl.textContent = `Regenerate Dub (${selectedCount})`;
  } else {
    lbl.textContent = "Regenerate Dub";
  }
}
window.updateRegenDubButtonCount = updateRegenDubButtonCount;

async function regenerateSelectedDub() {
  if (appState.subtitles.length === 0) {
    showToast("No subtitles available to regenerate dub. Please upload media or transcribe first.");
    return;
  }

  let selected = appState.subtitles.filter((s) => s.selected);
  if (selected.length === 0) {
    showToast("Please select at least one subtitle using the checkboxes to regenerate dub.");
    return;
  }

  const btn = ui.tbBtnRegenDub || document.getElementById("tbBtnRegenDub");
  const lbl = ui.tbBtnRegenDubLabel || document.getElementById("tbBtnRegenDubLabel");
  const origText = lbl ? lbl.textContent : "Regenerate Dub";

  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = `Regenerating Dub (${selected.length})...`;
  showToast(`Synthesizing Khmer voice dub for ${selected.length} subtitle(s)...`);

  try {
    const voice = (ui.selectVoiceModel ? ui.selectVoiceModel.value : "") || "km-KH-PisethNeural";
    const rateStr = getVoiceRateString();
    const pitchStr = getVoicePitchString();

    const res = await fetch("/api/tts/all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: appState.sessionId || `session_${Date.now()}`,
        segments: selected,
        voice: voice,
        rate: rateStr,
        pitch: pitchStr,
        volume: "+60%",
        auto_adjust_duration: true,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "TTS synthesis failed");
    }

    const data = await res.json();
    const updatedSegments = data.segments || [];
    const updatedMap = new Map(updatedSegments.map((s) => [s.id, s]));

    appState.subtitles.forEach((sub) => {
      if (updatedMap.has(sub.id)) {
        const u = updatedMap.get(sub.id);
        sub.audio_path = u.audio_path;
        sub.audio_url = u.audio_url;
        sub.actual_duration = u.actual_duration;
        if (u.start !== undefined) sub.start = u.start;
        if (u.end !== undefined) sub.end = u.end;
        sub.status = "Ready";
      }
    });

    renderSubtitlesTable();
    renderTimelineBlocks();
    updateStatusMetrics();
    showToast(`✅ Successfully regenerated dub for ${selected.length} subtitle(s)!`);

    // Preview the first regenerated audio segment
    const firstWithAudio = updatedSegments.find((s) => s.audio_url);
    if (firstWithAudio && firstWithAudio.audio_url) {
      appState.previewAudio.src = firstWithAudio.audio_url;
      appState.previewAudio.play().catch(() => { });
    }
  } catch (err) {
    console.error("Regenerate dub error:", err);
    showToast(`Error regenerating dub: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
    updateRegenDubButtonCount();
  }
}
window.regenerateSelectedDub = regenerateSelectedDub;

// --- Project Translation Execution ---
let translationPollTimer = null;

async function startProjectSubtitleTranslation() {
  if (appState.subtitles.length === 0) {
    showToast("No subtitles to translate. Please upload media or add subtitles first.");
    return;
  }

  const unlockedCount = appState.subtitles.filter((s) => !s.locked).length;
  if (unlockedCount === 0) {
    showToast("All subtitles are locked 🔒. Unlock at least one subtitle to translate.");
    return;
  }

  const projectId = appState.sessionId || "current_project";
  const provider = ui.selectProjectProvider ? ui.selectProjectProvider.value : appState.translationEngine.activeProvider;
  const model = ui.selectProjectModel ? ui.selectProjectModel.value : null;
  const style = ui.selectProjectStyle ? ui.selectProjectStyle.value : "natural";

  const storedGeminiKey = localStorage.getItem("khmerdub_gemini_api_key") || (ui.inputGeminiKey ? ui.inputGeminiKey.value.trim() : "") || (ui.inputGeminiCustomKey ? ui.inputGeminiCustomKey.value.trim() : "");
  const storedCodeCraftKey = localStorage.getItem("khmerdub_codecraft_api_key") || (ui.inputCodeCraftCustomKey ? ui.inputCodeCraftCustomKey.value.trim() : "");
  const storedCodeCraftBaseUrl = localStorage.getItem("khmerdub_codecraft_base_url") || (ui.inputCodeCraftBaseUrl ? ui.inputCodeCraftBaseUrl.value.trim() : "");
  const storedOpenAIKey = localStorage.getItem("khmerdub_openai_api_key") || (ui.inputOpenAICustomKey ? ui.inputOpenAICustomKey.value.trim() : "");
  const storedGoogleKey = localStorage.getItem("khmerdub_google_api_key") || (ui.inputGoogleCustomKey ? ui.inputGoogleCustomKey.value.trim() : "");

  // Pre-validate required API keys before making call
  if (provider === "gemini" && !storedGeminiKey && !appState.hasServerApiKey) {
    showToast("⚠️ Google Gemini API Key required. Please configure your key to proceed.");
    openApiKeyModal();
    return;
  }
  if (provider === "codecraft" && !storedCodeCraftKey) {
    showToast("⚠️ CodeCraft API Key required. Please configure it in AI Settings.");
    openAiSettingsModal();
    return;
  }
  if (provider === "openai" && !storedOpenAIKey) {
    showToast("⚠️ OpenAI API Key required. Please configure it in AI Settings.");
    openAiSettingsModal();
    return;
  }

  const reqCredentials = {
    gemini_api_key: storedGeminiKey,
    codecraft_api_key: storedCodeCraftKey,
    codecraft_base_url: storedCodeCraftBaseUrl,
    openai_api_key: storedOpenAIKey,
    google_api_key: storedGoogleKey,
    api_key: provider === "codecraft" ? storedCodeCraftKey : (provider === "openai" ? storedOpenAIKey : storedGeminiKey),
  };

  const options = {
    use_context: ui.chkUseContext ? ui.chkUseContext.checked : true,
    preserve_speaker: ui.chkPreserveSpeaker ? ui.chkPreserveSpeaker.checked : true,
    optimize_dubbing: ui.chkOptimizeDubbing ? ui.chkOptimizeDubbing.checked : true,
    use_translation_memory: ui.chkUseTM ? ui.chkUseTM.checked : true,
    use_glossary: ui.chkUseGlossary ? ui.chkUseGlossary.checked : true,
    enable_fallback: ui.chkEnableFallback ? ui.chkEnableFallback.checked : true,
    credentials: reqCredentials,
    api_key: reqCredentials.api_key,
    gemini_api_key: storedGeminiKey,
    codecraft_api_key: storedCodeCraftKey,
    openai_api_key: storedOpenAIKey,
  };

  appState.translationEngine.isTranslating = true;
  appState.translationEngine.activeJobId = `trans_${projectId}`;

  // UI state
  if (ui.translationLiveCard) {
    ui.translationLiveCard.classList.remove("hidden");
    if (ui.liveStatusTitle) ui.liveStatusTitle.textContent = `Translating dialogue via ${provider.toUpperCase()}...`;
    if (ui.liveProviderPill) ui.liveProviderPill.textContent = provider.toUpperCase();
    if (ui.liveProgressFill) ui.liveProgressFill.style.width = "10%";
    if (ui.liveProgressPct) ui.liveProgressPct.textContent = "10%";
    if (ui.liveProgressCount) ui.liveProgressCount.textContent = `0 / ${unlockedCount} segments`;
  }

  if (ui.btnTranslateSubtitlesProject) {
    ui.btnTranslateSubtitlesProject.disabled = true;
    if (ui.labelTranslateBtn) ui.labelTranslateBtn.textContent = "Translating...";
  }

  updateProjectStatus("Processing");
  showPlayerLoading(`Translating ${unlockedCount} segments via ${provider.toUpperCase()}...`);

  // Start polling translation status
  if (translationPollTimer) clearInterval(translationPollTimer);
  translationPollTimer = setInterval(async () => {
    try {
      const pollRes = await fetch(`/api/projects/${projectId}/translation-status`);
      if (pollRes.ok) {
        const pollData = await pollRes.json();
        if (pollData.job) {
          const pct = pollData.job.progress || 10;
          if (ui.liveProgressFill) ui.liveProgressFill.style.width = `${pct}%`;
          if (ui.liveProgressPct) ui.liveProgressPct.textContent = `${pct}%`;

          // Status message
          const statusMsg = pollData.job.status_message;
          if (statusMsg && ui.liveStatusTitle) ui.liveStatusTitle.textContent = statusMsg;

          // Per-segment live indicator
          const segIdx = pollData.job.current_segment_idx;
          const segText = pollData.job.current_segment_text;
          const totalSegs = pollData.job.total_segments || unlockedCount;
          if (segIdx && segText && ui.liveSegmentPreview) {
            ui.liveSegmentPreview.classList.remove("hidden");
            if (ui.liveSegmentLabel) ui.liveSegmentLabel.textContent = `Segment ${segIdx} / ${totalSegs}`;
            if (ui.liveSegmentText) ui.liveSegmentText.textContent = segText.length > 72 ? segText.slice(0, 72) + "…" : segText;
          }
        }
      }
    } catch (e) { }
  }, 1500);

  try {
    const res = await fetch(`/api/projects/${projectId}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: projectId,
        source_language: "en",
        target_language: "km",
        segments: appState.subtitles,
        provider,
        model,
        style,
        options,
        api_key: reqCredentials.api_key,
        credentials: reqCredentials,
      }),
    });

    clearInterval(translationPollTimer);

    if (res.ok) {
      const data = await res.json();
      if (!data.success && data.error) {
        const errMsg = data.error.message || "Failed to translate";
        showToast(`Translation error: ${errMsg}`);
        if (ui.liveStatusTitle) ui.liveStatusTitle.textContent = "Translation failed";
        if (data.error.code === "INVALID_API_KEY" || errMsg.includes("API Key")) {
          openApiKeyModal();
        }
        return;
      }
      const updatedSegments = data.segments || [];

      let modifiedCount = 0;
      updatedSegments.forEach((tSeg) => {
        const target = appState.subtitles.find((s) => s.id === tSeg.id);
        if (target && !target.locked && tSeg.khmer_text) {
          target.khmer_text = tSeg.khmer_text;
          if (tSeg.emotion) target.emotion = tSeg.emotion;
          target.status = "Ready";
          target.provider = data.provider || provider;
          target.tone = style;
          modifiedCount++;
        }
      });

      if (ui.liveProgressFill) ui.liveProgressFill.style.width = "100%";
      if (ui.liveProgressPct) ui.liveProgressPct.textContent = "100%";
      if (ui.liveProgressCount) ui.liveProgressCount.textContent = `${modifiedCount} / ${unlockedCount} translated`;
      if (ui.liveStatusTitle) ui.liveStatusTitle.textContent = "Translation Complete!";
      if (ui.liveSegmentPreview) ui.liveSegmentPreview.classList.add("hidden");

      renderSubtitlesTable();
      renderTimelineBlocks();
      updateStatusMetrics();
      showToast(`Translated ${modifiedCount} dialogue segments via ${data.provider?.toUpperCase() || provider.toUpperCase()}!`);
    } else {
      const err = await res.json();
      const errMsg = err.error?.message || err.detail || "Failed to translate";
      showToast(`Translation error: ${errMsg}`);
      if (ui.liveStatusTitle) ui.liveStatusTitle.textContent = "Translation failed";
      if (errMsg.includes("API Key") || (err.error && err.error.code === "INVALID_API_KEY")) {
        openApiKeyModal();
      }
    }
  } catch (err) {
    clearInterval(translationPollTimer);
    showToast(`Network error during translation: ${err.message}`);
    if (ui.liveStatusTitle) ui.liveStatusTitle.textContent = "Translation error";
  } finally {
    appState.translationEngine.isTranslating = false;
    updateProjectStatus("Draft");
    hidePlayerLoading();

    if (ui.btnTranslateSubtitlesProject) {
      ui.btnTranslateSubtitlesProject.disabled = false;
      if (ui.labelTranslateBtn) ui.labelTranslateBtn.textContent = "Translate Subtitles";
    }

    setTimeout(() => {
      if (ui.translationLiveCard && !appState.translationEngine.isTranslating) {
        ui.translationLiveCard.classList.add("hidden");
      }
    }, 4000);
  }
}

async function cancelProjectSubtitleTranslation() {
  const projectId = appState.sessionId || "current_project";
  try {
    await fetch(`/api/projects/${projectId}/translation/cancel`, { method: "POST" });
    if (translationPollTimer) clearInterval(translationPollTimer);
    appState.translationEngine.isTranslating = false;
    if (ui.liveStatusTitle) ui.liveStatusTitle.textContent = "Cancelled by user";
    showToast("Translation job cancelled.");
  } catch (err) {
    showToast(`Error cancelling: ${err.message}`);
  }
}

// Backward-compatible bridge for existing toolbar button
async function translateAllSubtitles() {
  return startProjectSubtitleTranslation();
}

// --- Project Glossary ---
async function loadGlossary() {
  const projectId = appState.sessionId || "current_project";
  if (!ui.tbodyGlossary) return;
  ui.tbodyGlossary.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:1.5rem;color:var(--text-tertiary);">Loading glossary...</td></tr>`;

  try {
    const res = await fetch(`/api/projects/${projectId}/glossary`);
    if (res.ok) {
      const data = await res.json();
      const terms = data.terms || [];

      if (terms.length === 0) {
        ui.tbodyGlossary.innerHTML = `
          <tr>
            <td colspan="4" style="text-align:center;padding:2rem;color:var(--text-tertiary);">
              No glossary terms defined yet. Add key terms above to enforce accurate Khmer terminology.
            </td>
          </tr>
        `;
        return;
      }

      ui.tbodyGlossary.innerHTML = "";
      terms.forEach((t) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${escapeHtml(t.source_term)}</strong></td>
          <td><span class="khmer-term-pill">${escapeHtml(t.target_term)}</span></td>
          <td style="color:var(--text-secondary);font-size:0.8rem;">${escapeHtml(t.notes || '')}</td>
          <td style="text-align:right;">
            <button type="button" class="btn-del-sm" title="Delete Term" onclick="deleteGlossaryTermHandler(${t.id})">
              &times;
            </button>
          </td>
        `;
        ui.tbodyGlossary.appendChild(tr);
      });
    }
  } catch (err) {
    ui.tbodyGlossary.innerHTML = `<tr><td colspan="4" style="color:var(--danger);padding:1rem;">Failed to load glossary: ${err.message}</td></tr>`;
  }
}

async function addGlossaryTermHandler() {
  const sourceTerm = ui.inputGlossarySource?.value.trim();
  const targetTerm = ui.inputGlossaryTarget?.value.trim();
  const notes = ui.inputGlossaryNotes?.value.trim() || "";
  const projectId = appState.sessionId || "current_project";

  if (!sourceTerm || !targetTerm) {
    showToast("Please enter both the English term and Khmer translation");
    return;
  }

  try {
    const res = await fetch(`/api/projects/${projectId}/glossary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_term: sourceTerm,
        target_term: targetTerm,
        notes,
      }),
    });

    if (res.ok) {
      if (ui.inputGlossarySource) ui.inputGlossarySource.value = "";
      if (ui.inputGlossaryTarget) ui.inputGlossaryTarget.value = "";
      if (ui.inputGlossaryNotes) ui.inputGlossaryNotes.value = "";
      showToast(`Glossary term "${sourceTerm}" added!`);
      loadGlossary();
    } else {
      showToast("Failed to add glossary term");
    }
  } catch (e) {
    showToast(`Glossary error: ${e.message}`);
  }
}

async function deleteGlossaryTermHandler(termId) {
  const projectId = appState.sessionId || "current_project";
  try {
    const res = await fetch(`/api/projects/${projectId}/glossary/${termId}`, { method: "DELETE" });
    if (res.ok) {
      showToast("Glossary term deleted");
      loadGlossary();
    }
  } catch (e) {
    showToast(`Error deleting term: ${e.message}`);
  }
}
window.deleteGlossaryTermHandler = deleteGlossaryTermHandler;

// --- Translation Memory ---
async function loadTranslationMemory() {
  const projectId = appState.sessionId || "current_project";
  if (!ui.tbodyTM) return;
  ui.tbodyTM.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:1.5rem;color:var(--text-tertiary);">Loading Translation Memory...</td></tr>`;

  try {
    const res = await fetch(`/api/projects/${projectId}/translation-memory?limit=100`);
    if (res.ok) {
      const data = await res.json();
      const items = data.items || [];

      if (items.length === 0) {
        ui.tbodyTM.innerHTML = `
          <tr>
            <td colspan="5" style="text-align:center;padding:2rem;color:var(--text-tertiary);">
              Translation Memory is currently empty. As subtitles are translated, identical dialogue lines will be cached here.
            </td>
          </tr>
        `;
        return;
      }

      ui.tbodyTM.innerHTML = "";
      items.forEach((item) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(item.source_text)}">
            ${escapeHtml(item.source_text)}
          </td>
          <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:var(--font-khmer);" title="${escapeHtml(item.translated_text)}">
            ${escapeHtml(item.translated_text)}
          </td>
          <td><span class="row-provider-pill">${escapeHtml(item.provider?.toUpperCase() || 'GEMINI')}</span></td>
          <td style="font-size:0.75rem;color:var(--text-tertiary);">${escapeHtml(item.created_at || '')}</td>
          <td style="text-align:right;">
            <button type="button" class="btn-del-sm" title="Delete TM Record" onclick="deleteTMHandler(${item.id})">
              &times;
            </button>
          </td>
        `;
        ui.tbodyTM.appendChild(tr);
      });
    }
  } catch (err) {
    ui.tbodyTM.innerHTML = `<tr><td colspan="5" style="color:var(--danger);padding:1rem;">Failed to load TM: ${err.message}</td></tr>`;
  }
}

async function deleteTMHandler(itemId) {
  try {
    const res = await fetch(`/api/translation-memory/${itemId}`, { method: "DELETE" });
    if (res.ok) {
      showToast("Translation Memory entry deleted");
      loadTranslationMemory();
    }
  } catch (e) {
    showToast(`Error deleting TM: ${e.message}`);
  }
}
window.deleteTMHandler = deleteTMHandler;

// --- Admin Monitoring Stats ---
async function loadAdminStats() {
  try {
    const res = await fetch("/api/admin/translation/stats");
    if (res.ok) {
      const data = await res.json();
      const s = data.stats || {};

      const totals = s.totals || {};
      const totalJobs = totals.total_jobs !== undefined ? totals.total_jobs : (s.total_runs || 0);
      const totalSegments = totals.total_translated_segments !== undefined ? totals.total_translated_segments : (s.total_segments || 0);
      const failedJobs = totals.total_failures !== undefined ? totals.total_failures : (s.failed_runs || 0);
      const avgLat = totals.overall_avg_duration_ms !== undefined ? Math.round(totals.overall_avg_duration_ms) : (s.avg_duration_ms || 0);

      if (ui.statTotalJobs) ui.statTotalJobs.textContent = totalJobs;
      if (ui.statTotalSegments) ui.statTotalSegments.textContent = totalSegments;
      if (ui.statFailedJobs) ui.statFailedJobs.textContent = failedJobs;
      if (ui.statAvgLatency) ui.statAvgLatency.textContent = `${avgLat}ms`;

      if (ui.tbodyProviderStats) {
        ui.tbodyProviderStats.innerHTML = "";
        const providers = s.providers || [];
        if (providers.length === 0) {
          ui.tbodyProviderStats.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:1.5rem;color:var(--text-tertiary);">No translation jobs recorded yet</td></tr>`;
        } else {
          providers.forEach((p) => {
            const totalReq = p.total_requests !== undefined ? p.total_requests : (p.total_runs || 0);
            const failedReq = p.failed_requests !== undefined ? p.failed_requests : (p.failed_runs || 0);
            const successRate = totalReq > 0 ? Math.round(((totalReq - failedReq) / totalReq) * 100) : 100;
            const segs = p.total_segments !== undefined ? p.total_segments : 0;
            const lat = p.avg_duration_ms ? Math.round(p.avg_duration_ms) : 0;
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td><strong>${escapeHtml(p.provider?.toUpperCase() || '')}</strong></td>
              <td>${totalReq}</td>
              <td>${segs}</td>
              <td>${lat}ms</td>
              <td><span class="provider-status-badge status-connected">${successRate}%</span></td>
            `;
            ui.tbodyProviderStats.appendChild(tr);
          });
        }
      }
    }
  } catch (err) {
    console.warn("Could not load admin stats:", err);
  }
}

// --- Single Segment Regeneration Modal ---
function openRegenerateModal(id, event) {
  if (event) event.stopPropagation();
  const sub = appState.subtitles.find((s) => s.id === id);
  if (!sub) return;

  appState.translationEngine.selectedSegmentForRegen = id;
  if (ui.regenSourceTextDisplay) {
    ui.regenSourceTextDisplay.textContent = sub.text || "(empty dialogue)";
  }
  if (ui.textRegenResult) {
    ui.textRegenResult.value = sub.khmer_text || "";
  }
  if (ui.selectRegenProvider) {
    ui.selectRegenProvider.value = sub.provider || appState.translationEngine.activeProvider || "gemini";
  }
  if (ui.selectRegenTone) {
    ui.selectRegenTone.value = sub.tone || "neutral";
  }
  if (ui.modalRegenerateSegment) {
    ui.modalRegenerateSegment.classList.remove("hidden");
  }
}
window.openRegenerateModal = openRegenerateModal;

function closeRegenerateModal() {
  const modal = ui.modalRegenerateSegment || document.getElementById("modalRegenerateSegment");
  if (modal) {
    modal.classList.add("hidden");
  }
  appState.translationEngine.selectedSegmentForRegen = null;
}
window.closeRegenerateModal = closeRegenerateModal;

async function doRegenerateSegment() {
  const segId = appState.translationEngine.selectedSegmentForRegen;
  if (!segId) return;
  const sub = appState.subtitles.find((s) => s.id === segId);
  if (!sub) return;

  const provider = ui.selectRegenProvider?.value || "gemini";
  const style = ui.selectRegenStyle?.value || "natural";
  const tone = ui.selectRegenTone?.value || "neutral";
  const duration = Math.max(0.5, (sub.end || 0) - (sub.start || 0));

  if (ui.btnDoRegenerate) {
    ui.btnDoRegenerate.disabled = true;
    ui.btnDoRegenerate.textContent = "Regenerating...";
  }

  try {
    const res = await fetch(`/api/subtitles/${segId}/regenerate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: sub.text,
        duration,
        provider,
        style,
        tone,
        project_id: appState.sessionId || "current_project",
      }),
    });

    const data = await res.json();
    if (data.success && data.translation) {
      if (ui.textRegenResult) {
        ui.textRegenResult.value = data.translation;
      }
      showToast(`Regenerated via ${provider.toUpperCase()} (${tone})`);
    } else {
      showToast(`Regeneration failed: ${data.message || "Error"}`);
    }
  } catch (e) {
    showToast(`Regeneration error: ${e.message}`);
  } finally {
    if (ui.btnDoRegenerate) {
      ui.btnDoRegenerate.disabled = false;
      ui.btnDoRegenerate.textContent = "Regenerate";
    }
  }
}

function applyRegenerateToSubtitle() {
  const segId = appState.translationEngine.selectedSegmentForRegen;
  if (!segId) return;
  const sub = appState.subtitles.find((s) => s.id === segId);
  if (!sub) return;

  const newText = ui.textRegenResult?.value.trim();
  if (!newText) {
    showToast("Please enter or generate translated text");
    return;
  }

  sub.khmer_text = newText;
  sub.provider = ui.selectRegenProvider?.value || "gemini";
  sub.tone = ui.selectRegenTone?.value || "neutral";
  sub.status = "Ready";

  closeRegenerateModal();
  renderSubtitlesTable();
  renderTimelineBlocks();
  showToast(`Updated subtitle #${segId}`);
}


function fixKhmerGrammar() {
  if (appState.subtitles.length === 0) return;
  appState.subtitles.forEach((s) => {
    if (s.khmer_text) {
      s.khmer_text = s.khmer_text.replace(/\s+/g, " ").trim();
      if (!s.khmer_text.endsWith("។") && !s.khmer_text.endsWith("?")) {
        s.khmer_text += "។";
      }
    }
  });
  renderSubtitlesTable();
  showToast("Khmer punctuation & spell correction applied");
}

function mergeSelectedSubtitles() {
  const activeIdx = appState.subtitles.findIndex((s) => s.id === appState.activeSubtitleId);
  if (activeIdx === -1 || activeIdx >= appState.subtitles.length - 1) {
    showToast("Select a subtitle with an adjacent row to merge");
    return;
  }
  const curr = appState.subtitles[activeIdx];
  const next = appState.subtitles[activeIdx + 1];

  curr.end = next.end;
  curr.text = `${curr.text || ''} ${next.text || ''}`.trim();
  curr.khmer_text = `${curr.khmer_text || ''} ${next.khmer_text || ''}`.trim();
  appState.subtitles.splice(activeIdx + 1, 1);

  renderSubtitlesTable();
  renderTimelineBlocks();
  updateStatusMetrics();
  showToast("Merged 2 adjacent subtitle rows");
}

function splitSelectedSubtitle() {
  const activeIdx = appState.subtitles.findIndex((s) => s.id === appState.activeSubtitleId);
  if (activeIdx === -1) {
    showToast("Please click a subtitle row to split");
    return;
  }
  const curr = appState.subtitles[activeIdx];
  const mid = parseFloat(((curr.start + curr.end) / 2).toFixed(1));
  const origWords = (curr.text || "").split(" ");
  const halfWords = Math.ceil(origWords.length / 2);

  const text1 = origWords.slice(0, halfWords).join(" ");
  const text2 = origWords.slice(halfWords).join(" ");

  curr.end = mid;
  curr.text = text1;

  const newSub = {
    id: Date.now(),
    start: mid,
    end: curr.end + Math.max(1, curr.end - curr.start),
    text: text2 || "Part 2...",
    khmer_text: curr.khmer_text || "",
    speaker: curr.speaker,
    voice: curr.voice,
    status: "Needs Review",
  };
  appState.subtitles.splice(activeIdx + 1, 0, newSub);

  renderSubtitlesTable();
  renderTimelineBlocks();
  updateStatusMetrics();
  showToast("Subtitle split into two segments");
}

function deleteSelectedSubtitle() {
  if (!appState.activeSubtitleId) return;
  deleteSubtitleRow(appState.activeSubtitleId);
}

function syncSubtitleTiming() {
  for (let i = 0; i < appState.subtitles.length - 1; i++) {
    const curr = appState.subtitles[i];
    const next = appState.subtitles[i + 1];
    if (curr.end > next.start) {
      curr.end = next.start;
    }
  }
  renderSubtitlesTable();
  renderTimelineBlocks();
  showToast("Subtitle timing synchronized seamlessly");
}

// Auto-Detect Character Speakers by Voice Pitch — shows preview modal before committing

// Holds pending diarization result while user previews
let _pendingVoiceAssignment = null;

function closeAutoVoicePreviewModal() {
  if (ui.modalAutoVoicePreview) ui.modalAutoVoicePreview.classList.add("hidden");
  _pendingVoiceAssignment = null;
}

function openAutoVoicePreviewModal(data) {
  const { segments, stats } = data;
  _pendingVoiceAssignment = segments;

  // Stats row
  if (ui.voiceStatMaleCount) ui.voiceStatMaleCount.textContent = stats.male_count || 0;
  if (ui.voiceStatFemaleCount) ui.voiceStatFemaleCount.textContent = stats.female_count || 0;

  // Boy & Girl stat cards (dynamic display)
  const boyCount = stats.boy_count || 0;
  const girlCount = stats.girl_count || 0;

  if (ui.voiceStatBoyCount) ui.voiceStatBoyCount.textContent = boyCount;
  if (ui.voiceStatCardBoy) ui.voiceStatCardBoy.style.display = boyCount > 0 ? "flex" : "none";
  if (ui.voiceStatSepBoy) ui.voiceStatSepBoy.style.display = boyCount > 0 ? "block" : "none";

  if (ui.voiceStatGirlCount) ui.voiceStatGirlCount.textContent = girlCount;
  if (ui.voiceStatCardGirl) ui.voiceStatCardGirl.style.display = girlCount > 0 ? "flex" : "none";
  if (ui.voiceStatSepGirl) ui.voiceStatSepGirl.style.display = girlCount > 0 ? "block" : "none";

  // Single speaker notice
  if (ui.voiceSingleSpeakerNotice) {
    ui.voiceSingleSpeakerNotice.classList.toggle("hidden", !stats.is_single_speaker);
  }

  // Build preview table (show all segments, max 50 displayed)
  if (ui.voiceAssignTableBody) {
    const preview = segments.slice(0, 50);
    ui.voiceAssignTableBody.innerHTML = preview.map((seg, i) => {
      const v = seg.voice || "Khmer Male 01";
      let speakerTag = `<span class="va-tag-male">♂ ${escapeHtml(seg.speaker || "Speaker 1")}</span>`;
      let voiceName = "Piseth (Male)";
      if (v === "Khmer Female 01") {
        speakerTag = `<span class="va-tag-female">♀ ${escapeHtml(seg.speaker || "Speaker 2")}</span>`;
        voiceName = "Sreymom (Female)";
      } else if (v === "Khmer Boy 01") {
        speakerTag = `<span class="va-tag-boy" style="background:rgba(59,130,246,0.15);color:#60a5fa;border:1px solid rgba(59,130,246,0.3);padding:2px 8px;border-radius:12px;font-size:11px;">👦 ${escapeHtml(seg.speaker || "Speaker 3 (Boy)")}</span>`;
        voiceName = "Piseth (Boy)";
      } else if (v === "Khmer Girl 01") {
        speakerTag = `<span class="va-tag-girl" style="background:rgba(236,72,153,0.15);color:#f472b6;border:1px solid rgba(236,72,153,0.3);padding:2px 8px;border-radius:12px;font-size:11px;">👧 ${escapeHtml(seg.speaker || "Speaker 3 (Girl)")}</span>`;
        voiceName = "Sreymom (Girl)";
      }
      const voiceBadge = `<span class="va-voice-badge">${voiceName}</span>`;
      const startStr = formatTimecodePrecise(seg.start || 0);
      const textPreview = (seg.text || "").slice(0, 60) + ((seg.text || "").length > 60 ? "…" : "");
      return `<tr>
        <td>${i + 1}</td>
        <td>${startStr}</td>
        <td title="${escapeHtml(seg.text || '')}">${escapeHtml(textPreview)}</td>
        <td>${speakerTag}</td>
        <td>${voiceBadge}</td>
      </tr>`;
    }).join("");
  }

  // Footnote
  if (ui.voiceAssignFootnote) {
    const shown = Math.min(segments.length, 50);
    ui.voiceAssignFootnote.textContent = segments.length > 50
      ? `Showing ${shown} of ${segments.length} segments. Click "Confirm & Apply" to assign all.`
      : `${segments.length} segments analyzed. Click "Confirm & Apply" to update all subtitles.`;
  }

  // Wire confirm button
  if (ui.btnConfirmAutoVoice) {
    // Remove old listener to prevent duplicates
    const fresh = ui.btnConfirmAutoVoice.cloneNode(true);
    ui.btnConfirmAutoVoice.parentNode.replaceChild(fresh, ui.btnConfirmAutoVoice);
    ui.btnConfirmAutoVoice = fresh;
    fresh.addEventListener("click", () => {
      if (!_pendingVoiceAssignment) return;
      const idMap = new Map(_pendingVoiceAssignment.map((s) => [s.id, s]));
      appState.subtitles.forEach((s) => {
        const found = idMap.get(s.id);
        if (found) {
          s.speaker = found.speaker || s.speaker;
          s.voice = found.voice || s.voice;
          if (found.emotion) s.emotion = found.emotion;
        }
      });
      closeAutoVoicePreviewModal();
      renderSubtitlesTable();
      renderTimelineBlocks();
      const parts = [];
      if (stats.male_count) parts.push(`${stats.male_count} Piseth ♂`);
      if (stats.female_count) parts.push(`${stats.female_count} Sreymom ♀`);
      if (stats.boy_count) parts.push(`${stats.boy_count} Boy 👦`);
      if (stats.girl_count) parts.push(`${stats.girl_count} Girl 👧`);
      showToast(`✅ Voice assignment applied: ${parts.join(" · ") || `${segments.length} segments`}`);
    });
  }

  if (ui.modalAutoVoicePreview) ui.modalAutoVoicePreview.classList.remove("hidden");
}

async function detectAndAssignSpeakers() {
  if (!appState.sessionId || appState.subtitles.length === 0) {
    showToast("Please upload a video or generate subtitles first.");
    return;
  }
  showToast("Analyzing voice pitch — preparing preview...");
  showPlayerLoading("Analyzing voice pitch & identifying speakers...");
  try {
    const res = await fetch("/api/stt/diarize/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: appState.sessionId,
        engine: "whisper",
        segments: appState.subtitles,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Speaker detection failed");
    }
    const data = await res.json();
    hidePlayerLoading();
    if (data.segments && data.segments.length > 0) {
      openAutoVoicePreviewModal(data);
    } else {
      showToast("No speaker data returned. Try uploading audio and transcribing first.");
    }
  } catch (e) {
    console.error("Speaker diarization error:", e);
    showToast(`Speaker detection error: ${e.message}`);
    hidePlayerLoading();
  }
}

async function detectDialogueEmotions() {
  if (!appState.subtitles || appState.subtitles.length === 0) {
    showToast("Please add or generate subtitles first.");
    return;
  }

  const btn = ui.tbBtnDetectEmotions || document.getElementById("tbBtnDetectEmotions");
  if (btn) {
    btn.disabled = true;
    btn.classList.add("loading");
  }

  showToast("Analyzing dialogue emotions & tone modulation...");
  showPlayerLoading("Analyzing emotional cues and voice tone modulation...");

  try {
    const payloadSegments = appState.subtitles.map((s, idx) => ({
      id: s.id !== undefined ? s.id : idx + 1,
      text: s.text || "",
      khmer_text: s.khmer || s.khmer_text || s.text || "",
      speaker: s.speaker || "Speaker 1",
      emotion: s.emotion || "neutral",
      pacing: s.pacing || "normal"
    }));

    const res = await fetch("/api/tts/detect-emotions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: appState.sessionId,
        api_key: appState.geminiApiKey || undefined,
        segments: payloadSegments
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Emotion detection failed");
    }

    const data = await res.json();
    hidePlayerLoading();

    if (data.segments && data.segments.length > 0) {
      const emoMap = new Map();
      data.segments.forEach(seg => {
        emoMap.set(seg.id, seg);
      });

      let changedCount = 0;
      appState.subtitles.forEach((s, idx) => {
        const segId = s.id !== undefined ? s.id : idx + 1;
        const match = emoMap.get(segId);
        if (match) {
          if (match.emotion) s.emotion = match.emotion;
          if (match.pacing) s.pacing = match.pacing;
          if (match.khmer_text && (!s.khmer || s.khmer.includes("["))) {
            s.khmer = match.khmer_text;
          }
          changedCount++;
        }
      });

      renderSubtitlesTable();
      if (typeof updateStatusCounters === "function") {
        updateStatusCounters();
      }
      showToast(`✨ Analyzed emotions and prosodic tones for ${changedCount} dialogue lines!`);
    } else {
      showToast("No emotional updates returned.");
    }
  } catch (err) {
    console.error("Emotion detection error:", err);
    showToast(`Emotion detection error: ${err.message}`);
    hidePlayerLoading();
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.classList.remove("loading");
    }
  }
}

window.detectDialogueEmotions = detectDialogueEmotions;

// Find & Replace
function openFindReplaceModal() {
  const modal = ui.modalFindReplace || document.getElementById("modalFindReplace");
  if (modal) {
    modal.classList.remove("hidden");
    if (ui.inputFindText) ui.inputFindText.focus();
  }
}

function closeFindReplaceModal() {
  const modal = ui.modalFindReplace || document.getElementById("modalFindReplace");
  if (modal) modal.classList.add("hidden");
}

window.openFindReplaceModal = openFindReplaceModal;
window.closeFindReplaceModal = closeFindReplaceModal;
window.closeAutoVoicePreviewModal = closeAutoVoicePreviewModal;

function applyFindAndReplace() {
  const findVal = ui.inputFindText.value.trim();
  const replaceVal = ui.inputReplaceText.value;
  if (!findVal) {
    showToast("Enter a word to find");
    return;
  }

  const targetCol = document.querySelector('input[name="findTarget"]:checked').value;
  let count = 0;

  appState.subtitles.forEach((s) => {
    if ((targetCol === "all" || targetCol === "orig") && s.text && s.text.includes(findVal)) {
      s.text = s.text.replaceAll(findVal, replaceVal);
      count++;
    }
    if ((targetCol === "all" || targetCol === "khmer") && s.khmer_text && s.khmer_text.includes(findVal)) {
      s.khmer_text = s.khmer_text.replaceAll(findVal, replaceVal);
      count++;
    }
  });

  renderSubtitlesTable();
  closeFindReplaceModal();
  showToast(`Replaced ${count} occurrences of "${findVal}"`);
}

// Pagination Controls
function renderPagination(currPage, totalPages) {
  ui.btnPagePrev.disabled = currPage <= 1;
  ui.btnPageNext.disabled = currPage >= totalPages;

  ui.pageNumbersList.innerHTML = "";
  for (let p = 1; p <= totalPages; p++) {
    const btn = document.createElement("button");
    btn.className = `page-num-btn ${p === currPage ? "active" : ""}`;
    btn.textContent = p;
    btn.onclick = () => {
      appState.currentPage = p;
      renderSubtitlesTable();
    };
    ui.pageNumbersList.appendChild(btn);
  }
}

function changePage(delta) {
  appState.currentPage += delta;
  renderSubtitlesTable();
}

// ==========================================================================
// 5. Timeline Synchronization Component
// ==========================================================================
function renderTimelineBlocks() {
  ui.timelineBlocksContainer.innerHTML = "";
  const total = appState.duration;

  if (total <= 0 || appState.subtitles.length === 0) return;

  appState.subtitles.forEach((sub) => {
    const leftPct = Math.max(0, (sub.start / total) * 100);
    const widthPct = Math.max(1.5, ((sub.end - sub.start) / total) * 100);

    let blockSpeakerClass = "block-male";
    const rawSpk = (sub.speaker || "").toLowerCase();
    const rawVox = (sub.voice || "").toLowerCase();
    if (rawSpk.includes("speaker 2") || rawSpk.includes("female") || rawVox.includes("female")) {
      blockSpeakerClass = "block-female";
    } else if (rawSpk.includes("girl") || rawVox.includes("girl")) {
      blockSpeakerClass = "block-girl";
    } else if (rawSpk.includes("boy") || rawVox.includes("boy")) {
      blockSpeakerClass = "block-boy";
    } else if (rawSpk.includes("narrator")) {
      blockSpeakerClass = "block-narrator";
    }

    const block = document.createElement("div");
    block.className = `timeline-block ${blockSpeakerClass} ${sub.id === appState.activeSubtitleId ? "block-active" : ""}`;
    block.id = `time-block-${sub.id}`;
    block.style.left = `${leftPct}%`;
    block.style.width = `${widthPct}%`;
    block.title = `${sub.text || 'Dialogue'} (${formatTimecodeSimple(sub.start)} - ${formatTimecodeSimple(sub.end)})`;

    block.innerHTML = `
      <div class="trim-handle start" data-handle="start" title="Drag to trim start"></div>
      <span class="timeline-block-label">${escapeHtml(sub.khmer_text || sub.text || "Segment")}</span>
      <div class="trim-handle end" data-handle="end" title="Drag to trim end"></div>
    `;

    // Interactive Dragging & Trimming for Timeline Block
    let blockDragMode = null; // 'start', 'end', 'move'
    let startClientX = 0;
    let initialStart = sub.start;
    let initialEnd = sub.end;

    function onBlockPointerDown(e) {
      if (e.button !== undefined && e.button !== 0) return;
      const trimHandle = e.target.closest(".trim-handle");
      if (trimHandle && trimHandle.dataset.handle) {
        blockDragMode = trimHandle.dataset.handle;
      } else {
        blockDragMode = "move";
      }

      startClientX = e.clientX;
      initialStart = sub.start;
      initialEnd = sub.end;

      selectAndSeekSubtitle(sub);

      e.stopPropagation();
      e.preventDefault();

      window.addEventListener("pointermove", onBlockPointerMove);
      window.addEventListener("pointerup", onBlockPointerUp);
      window.addEventListener("pointercancel", onBlockPointerUp);
    }

    function onBlockPointerMove(e) {
      if (!blockDragMode) return;
      const rect = ui.timelineBlocksContainer.getBoundingClientRect();
      if (!rect.width) return;

      const deltaSeconds = ((e.clientX - startClientX) / rect.width) * appState.duration;

      if (blockDragMode === "start") {
        const newStart = Math.max(0, Math.min(initialEnd - 0.2, initialStart + deltaSeconds));
        sub.start = parseFloat(newStart.toFixed(2));
      } else if (blockDragMode === "end") {
        const newEnd = Math.max(initialStart + 0.2, Math.min(appState.duration, initialEnd + deltaSeconds));
        sub.end = parseFloat(newEnd.toFixed(2));
      } else if (blockDragMode === "move") {
        const dur = initialEnd - initialStart;
        let newStart = initialStart + deltaSeconds;
        let newEnd = initialEnd + deltaSeconds;
        if (newStart < 0) {
          newStart = 0;
          newEnd = dur;
        }
        if (newEnd > appState.duration) {
          newEnd = appState.duration;
          newStart = Math.max(0, newEnd - dur);
        }
        sub.start = parseFloat(newStart.toFixed(2));
        sub.end = parseFloat(newEnd.toFixed(2));
      }

      // Update block position live
      const newLeftPct = Math.max(0, (sub.start / total) * 100);
      const newWidthPct = Math.max(1.5, ((sub.end - sub.start) / total) * 100);
      block.style.left = `${newLeftPct}%`;
      block.style.width = `${newWidthPct}%`;

      // Live update table row & quick editor
      const row = document.getElementById(`sub-row-${sub.id}`);
      if (row) {
        const startInput = row.querySelector(".col-start input");
        const endInput = row.querySelector(".col-end input");
        if (startInput) startInput.value = formatTimecodePrecise(sub.start);
        if (endInput) endInput.value = formatTimecodePrecise(sub.end);
      }
      syncSubtitleQuickEditor(sub);
      updateVideoSubtitleOverlay(appState.currentTime);
    }

    function onBlockPointerUp() {
      if (blockDragMode) {
        pushSubtitleHistory("Trim subtitle timeline block");
        blockDragMode = null;
        validateAndMarkSubtitle(sub);
        renderTimelineBlocks();
        renderSubtitlesTable();
        updateStatusMetrics();
      }
      window.removeEventListener("pointermove", onBlockPointerMove);
      window.removeEventListener("pointerup", onBlockPointerUp);
      window.removeEventListener("pointercancel", onBlockPointerUp);
    }

    // Overflow visual indicator: red zone at right edge of block if it exceeds video end
    if (appState.duration > 0) {
      const subEnd = parseFloat(sub.end) || 0;
      if (subEnd > appState.duration + 0.005) {
        const overflowAmt = Math.round((subEnd - appState.duration) * 100) / 100;
        block.classList.add('block-overflow');
        block.setAttribute('title',
          `Overflow +${overflowAmt.toFixed(2)}s | ${sub.text || 'Dialogue'} (${formatTimecodeSimple(sub.start)} - ${formatTimecodeSimple(subEnd)})`);
        const overflowEl = document.createElement('div');
        overflowEl.className = 'timeline-overflow-indicator';
        const blockDur = subEnd - (parseFloat(sub.start) || 0);
        const overflowPct = blockDur > 0 ? (overflowAmt / blockDur) * 100 : 10;
        overflowEl.style.width = `${Math.min(80, Math.max(4, overflowPct))}%`;
        overflowEl.title = `+${overflowAmt.toFixed(2)}s beyond video end`;
        block.appendChild(overflowEl);
      }
    }

    block.addEventListener("pointerdown", onBlockPointerDown);

    ui.timelineBlocksContainer.appendChild(block);
  });
}

// ==========================================================================
// 6. Bottom Status Bar & Generation Workflows
// ==========================================================================
function updateStatusMetrics() {
  const total = appState.subtitles.length;
  const translated = appState.subtitles.filter((s) => Boolean(s.khmer_text) && s.status !== "Needs Review").length;
  const review = appState.subtitles.filter((s) => s.status === "Needs Review").length;

  ui.statTotalSubs.textContent = total;
  ui.statTranslated.textContent = translated;
  ui.statNeedsReview.textContent = review;

  if (appState.dubbedVideoUrl) {
    ui.audioSyncBadgeText.textContent = "Audio synchronized";
  } else {
    ui.audioSyncBadgeText.textContent = "Audio standby";
  }
}

function updateProjectStatus(status) {
  appState.projectStatus = status;
  ui.projectStatusText.textContent = status;
  ui.projectStatusBadge.className = `project-status-badge status-${status.toLowerCase()}`;
}

async function triggerGeneratePipeline() {
  if (!appState.sessionId) {
    showToast("Please upload a video file first.");
    ui.hiddenVideoUpload.click();
    return;
  }

  // If subtitles not transcribed yet, run auto-transcription first!
  if (appState.subtitles.length === 0) {
    showToast("✨ Auto-transcribing dialogue first...");
    await triggerAutoTranscription();
    if (appState.subtitles.length === 0) {
      showToast("No subtitles found. Please click 'Auto Generate' in Subtitle Studio.");
      return;
    }
  }

  // If any segment lacks Khmer translation, auto-translate
  const needsTranslation = appState.subtitles.some((s) => !s.khmer_text);
  if (needsTranslation) {
    showToast("✨ Auto-translating subtitles to Khmer...");
    await translateAllSubtitles();
  }

  // Timeline validation gate: block export on unresolved critical issues
  if (appState.duration > 0 && appState.subtitles.length > 0) {
    const exportCheck = TimelineValidator.validateBeforeExport(appState.subtitles, appState.duration);
    if (!exportCheck.canExport) {
      showTimelineErrorModal(exportCheck.blockers);
      return;
    }
  }

  const isMuteDub = (appState.dubbingMode === "mute" || Boolean(ui.chkMuteOriginalAudio && ui.chkMuteOriginalAudio.checked));
  const isFastDub = !isMuteDub && (appState.dubbingMode !== "hq");

  updateProjectStatus("Processing");
  ui.btnGenerateDub.disabled = true;
  ui.btnGenerateFinal.disabled = true;
  showPlayerLoading(isMuteDub ? "🔇 Mute Dubbing: Synthesizing Khmer voices and muting original audio..." : (isFastDub ? "⚡ Fast Dubbing: Synthesizing Khmer voices and rendering video..." : "Synthesizing Khmer audio and rendering dubbed video..."));

  ui.pipelineStepCaption.textContent = isMuteDub ? "🔇 Mute Dubbing: Synthesizing Khmer speech (Edge-TTS)..." : (isFastDub ? "⚡ Fast Dubbing: Synthesizing Khmer speech (Edge-TTS)..." : "Synthesizing Khmer neural voices (Edge-TTS)...");
  ui.pipelineProgressFill.style.width = "20%";
  ui.progressPctText.textContent = "20%";
  ui.estTimeText.textContent = isMuteDub ? "~2-5s (⚡ Instant Mute & Replace)" : (isFastDub ? "~10-15s (⚡ Fast Track)" : "~2-3 minutes (Studio HQ)");

  try {
    // Step 1: Ensure Khmer voice synthesis is executed if any segment lacks audio
    const needsTts = appState.subtitles.some((s) => !s.audio_path);
    if (needsTts) {
      ui.pipelineStepCaption.textContent = (isFastDub || isMuteDub) ? "⚡ Parallel Edge-TTS synthesis..." : "Synthesizing Edge-TTS Khmer speech for segments...";
      ui.pipelineProgressFill.style.width = "35%";
      ui.progressPctText.textContent = "35%";

      const ttsRes = await fetch("/api/tts/all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: appState.sessionId,
          segments: prepareSegmentsForApi(appState.subtitles),
          voice: (ui.selectVoiceModel ? ui.selectVoiceModel.value : "") || "km-KH-PisethNeural",
          rate: getVoiceRateString(),
          pitch: getVoicePitchString(),
          volume: "+60%",
          auto_adjust_duration: true,
        }),
      });

      if (ttsRes.ok) {
        const ttsData = await ttsRes.json();
        appState.subtitles = sanitizeSubtitleTimelines(ttsData.segments || appState.subtitles, 0.25);
        renderSubtitlesTable();
        renderTimelineBlocks();
      } else {
        throw new Error("TTS voice synthesis failed during dubbing pipeline");
      }
    }

    // Step 2: Render dubbed video with stitched audio and isolated BGM
    const renderStepMsg = isMuteDub ? "🔇 Mute Dubbing: Stitching audio & replacing original audio in video..." : (isFastDub ? "⚡ Fast Dubbing: Instant BGM phase cancellation & FFmpeg mixing..." : "Stitching audio tracks & rendering dubbed video with FFmpeg...");
    showPlayerLoading(renderStepMsg);
    ui.pipelineStepCaption.textContent = renderStepMsg;
    ui.pipelineProgressFill.style.width = "65%";
    ui.progressPctText.textContent = "65%";

    const chosenVocalMethod = (isFastDub || isMuteDub) ? "fast_dsp" : ((ui.selVocalRemovalMethod && ui.selVocalRemovalMethod.value) || (document.getElementById("selVocalRemovalMethod") || {}).value || "fast_dsp");

    let finalDubMode = "bgm_isolate";
    if (isMuteDub) {
      finalDubMode = "replace";
    } else if (ui.chkPreserveBGM && ui.chkPreserveBGM.checked) {
      finalDubMode = "bgm_isolate";
    } else {
      finalDubMode = "ducking";
    }

    appState.subtitles = sanitizeSubtitleTimelines(appState.subtitles, 0.25);
    const res = await fetch("/api/dub", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: appState.sessionId,
        segments: prepareSegmentsForApi(appState.subtitles),
        mode: finalDubMode,
        vocal_removal_method: chosenVocalMethod,
        ducking_volume: 0.12,
        bgm_volume: 0.35,
        dub_volume: 1.40,
        blur_subtitles: appState.blurStudio.enabled,
        subtitle_blur_coords: {
          x: appState.blurSettings.x,
          y: appState.blurSettings.y,
          w: appState.blurSettings.w,
          h: appState.blurSettings.h,
          strength: appState.blurSettings.strength,
        },
        blur_objects: appState.blurStudio.enabled ? appState.blurStudio.objects.filter((o) => o.enabled) : [],
        aspect_ratio: appState.blurSettings.aspectRatio,
        canvas_blur_strength: 25,
        burn_subtitles: Boolean(ui.chkBurnSubtitlesExport && ui.chkBurnSubtitlesExport.checked),
        subtitle_style: appState.subtitleStyle,
        subtitle_language_mode: appState.subtitleStyle.langMode || "khmer",
      }),
    });

    if (!res.ok) {
      let detail = "Dubbing mix failed";
      try {
        const err = await res.json();
        detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail || err);
      } catch (_) {}
      throw new Error(detail);
    }

    const data = await res.json();
    appState.dubbedVideoUrl = data.dubbed_video_url;
    appState.dubbedAudioUrl = data.dubbed_audio_url;

    // Configure export links
    if (data.dubbed_video_url) ui.downloadVideoBtn.href = data.dubbed_video_url;
    if (data.dubbed_audio_url) ui.downloadAudioBtn.href = data.dubbed_audio_url;
    if (data.khmer_ass_url && ui.downloadKhmerAssBtn) ui.downloadKhmerAssBtn.href = data.khmer_ass_url;
    if (data.khmer_srt_url) ui.downloadKhmerSrtBtn.href = data.khmer_srt_url;
    if (data.khmer_vtt_url) ui.downloadKhmerVttBtn.href = data.khmer_vtt_url;
    if (data.original_srt_url) ui.downloadOrigSrtBtn.href = data.original_srt_url;

    ui.pipelineProgressFill.style.width = "100%";
    ui.progressPctText.textContent = "100%";
    ui.pipelineStepCaption.textContent = "Dubbed video rendered successfully!";

    updateProjectStatus("Completed");
    switchAudioTrack("dubbed");
    updateStatusMetrics();
    showToast("🎉 Khmer Dubbed Video Generated Successfully!");

    setTimeout(() => {
      openExportModal();
    }, 1200);

  } catch (err) {
    console.error("Dubbing error:", err);
    showToast(`Dubbing failed: ${err.message}`);
    updateProjectStatus("Draft");
  } finally {
    ui.btnGenerateDub.disabled = false;
    ui.btnGenerateFinal.disabled = false;
    hidePlayerLoading();
  }
}

function setDubbingMode(mode) {
  appState.dubbingMode = mode;
  try {
    localStorage.setItem("dubstudio_dubbing_mode", mode);
  } catch (e) { }

  if (ui.btnModeFastDub) {
    ui.btnModeFastDub.classList.toggle("active", mode === "fast");
    ui.btnModeFastDub.style.border = mode === "fast" ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid rgba(255, 255, 255, 0.08)";
    ui.btnModeFastDub.style.background = mode === "fast" ? "rgba(16, 185, 129, 0.12)" : "rgba(255, 255, 255, 0.03)";
    ui.btnModeFastDub.style.color = mode === "fast" ? "#34d399" : "#94a3b8";
  }
  if (ui.btnModeHqDub) {
    ui.btnModeHqDub.classList.toggle("active", mode === "hq");
    ui.btnModeHqDub.style.border = mode === "hq" ? "1px solid rgba(56, 189, 248, 0.4)" : "1px solid rgba(255, 255, 255, 0.08)";
    ui.btnModeHqDub.style.background = mode === "hq" ? "rgba(56, 189, 248, 0.12)" : "rgba(255, 255, 255, 0.03)";
    ui.btnModeHqDub.style.color = mode === "hq" ? "#38bdf8" : "#94a3b8";
  }
  if (ui.btnModeMuteDub) {
    ui.btnModeMuteDub.classList.toggle("active", mode === "mute");
    ui.btnModeMuteDub.style.border = mode === "mute" ? "1px solid rgba(245, 158, 11, 0.4)" : "1px solid rgba(255, 255, 255, 0.08)";
    ui.btnModeMuteDub.style.background = mode === "mute" ? "rgba(245, 158, 11, 0.12)" : "rgba(255, 255, 255, 0.03)";
    ui.btnModeMuteDub.style.color = mode === "mute" ? "#fbbf24" : "#94a3b8";
  }
  if (ui.chkMuteOriginalAudio) {
    ui.chkMuteOriginalAudio.checked = (mode === "mute");
  }
  if (ui.badgeDubbingSpeed) {
    if (mode === "fast") {
      ui.badgeDubbingSpeed.textContent = "⚡ Fast Track (~10s)";
      ui.badgeDubbingSpeed.style.background = "rgba(16, 185, 129, 0.18)";
      ui.badgeDubbingSpeed.style.color = "#34d399";
    } else if (mode === "mute") {
      ui.badgeDubbingSpeed.textContent = "🔇 Mute Orig (~2s)";
      ui.badgeDubbingSpeed.style.background = "rgba(245, 158, 11, 0.18)";
      ui.badgeDubbingSpeed.style.color = "#fbbf24";
    } else {
      ui.badgeDubbingSpeed.textContent = "🎬 Studio HQ (~2m)";
      ui.badgeDubbingSpeed.style.background = "rgba(56, 189, 248, 0.18)";
      ui.badgeDubbingSpeed.style.color = "#38bdf8";
    }
  }
  if (ui.estTimeText) {
    if (mode === "fast") {
      ui.estTimeText.textContent = "~10-15s (⚡ Fast Track)";
    } else if (mode === "mute") {
      ui.estTimeText.textContent = "~2-5s (⚡ Instant Mute & Replace)";
    } else {
      ui.estTimeText.textContent = "~2-3 minutes (Studio HQ)";
    }
  }
}
window.setDubbingMode = setDubbingMode;

function bindDubbingModeEvents() {
  if (ui.btnModeFastDub) {
    ui.btnModeFastDub.addEventListener("click", () => {
      setDubbingMode("fast");
      showToast("⚡ Fast Dubbing Activated (Instant DSP Phase Cancellation & Fast Mixing)");
    });
  }
  if (ui.btnModeHqDub) {
    ui.btnModeHqDub.addEventListener("click", () => {
      setDubbingMode("hq");
      showToast("🎬 Studio HQ Dubbing Activated (Deep AI Neural Demucs Vocal Separation)");
    });
  }
  if (ui.btnModeMuteDub) {
    ui.btnModeMuteDub.addEventListener("click", () => {
      setDubbingMode("mute");
      showToast("🔇 Mute Original Audio Activated (Completely mutes original video audio, zero vocal separation delay)");
    });
  }
  if (ui.chkMuteOriginalAudio) {
    ui.chkMuteOriginalAudio.addEventListener("change", (e) => {
      if (e.target.checked) {
        setDubbingMode("mute");
        showToast("🔇 Mute Original Audio Activated");
      } else {
        setDubbingMode("fast");
        showToast("⚡ Fast Dubbing Restored");
      }
    });
  }
}

// SRT Import & Export
function handleSrtImport(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (event) => {
    const text = event.target.result;
    const parsed = parseSrtContent(text);
    if (parsed.length > 0) {
      appState.subtitles = sanitizeSubtitleTimelines(parsed, 0.25);
      runTimelineValidation();
      showToast(`Imported ${parsed.length} subtitles from SRT!`);
    } else {
      showToast("Could not parse SRT file format");
    }
  };
  reader.readAsText(file);
}

function parseSrtContent(content) {
  const normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const blocks = normalized.split("\n\n");
  const result = [];

  blocks.forEach((block, idx) => {
    const lines = block.trim().split("\n");
    if (lines.length >= 3) {
      const timeLine = lines[1];
      const timeParts = timeLine.split("-->");
      if (timeParts.length === 2) {
        const start = parseTimecode(timeParts[0].trim());
        const end = parseTimecode(timeParts[1].trim());
        const subText = lines.slice(2).join(" ");
        result.push({
          id: idx + 1,
          start,
          end,
          text: subText,
          khmer_text: subText,
          speaker: "Speaker 1",
          voice: "Khmer Female 01",
          status: "Ready",
        });
      }
    }
  });
  return result;
}

function exportCurrentSubtitlesSrt() {
  if (appState.subtitles.length === 0) {
    showToast("No subtitles to export.");
    return;
  }
  let srtContent = "";
  appState.subtitles.forEach((s, idx) => {
    const startStr = formatTimecodePrecise(s.start).replace(".", ",");
    const endStr = formatTimecodePrecise(s.end).replace(".", ",");
    srtContent += `${idx + 1}\n00:${startStr} --> 00:${endStr}\n${s.khmer_text || s.text}\n\n`;
  });

  const blob = new Blob([srtContent], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${appState.projectName}_subtitles.srt`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("Downloaded Khmer SRT Subtitles");
}

// Local Storage & Config
function saveProjectLocally() {
  const projectData = {
    projectName: appState.projectName,
    subtitles: appState.subtitles,
    savedAt: new Date().toISOString(),
  };
  localStorage.setItem("dubstudio_project_data", JSON.stringify(projectData));
  showToast(`💾 Saved "${appState.projectName}" successfully!`);
}

function loadSavedPreferences() {
  const saved = localStorage.getItem("dubstudio_project_data");
  if (saved) {
    try {
      const data = JSON.parse(saved);
      if (data.projectName) {
        appState.projectName = data.projectName;
        ui.inputProjectName.value = data.projectName;
      }
    } catch (e) { }
  }
  const key = localStorage.getItem("khmerdub_gemini_api_key");
  if (key) {
    ui.inputGeminiKey.value = key;
    if (ui.inputGeminiCustomKey) ui.inputGeminiCustomKey.value = key;
    appState.geminiApiKey = key;
    ui.keyIconDot.classList.add("active");
  } else {
    // If not in localStorage, restore from server (.env / SQLite database)
    fetch("/api/settings/gemini-key")
      .then(res => res.json())
      .then(data => {
        if (data && data.key) {
          localStorage.setItem("khmerdub_gemini_api_key", data.key);
          appState.geminiApiKey = data.key;
          if (ui.inputGeminiKey) ui.inputGeminiKey.value = data.key;
          if (ui.inputGeminiCustomKey) ui.inputGeminiCustomKey.value = data.key;
          if (ui.keyIconDot) ui.keyIconDot.classList.add("active");
          updateAllProviderStatusBadges();
        }
      })
      .catch(() => {});
  }
  const openKey = localStorage.getItem("khmerdub_openai_api_key");
  if (openKey && ui.inputOpenAICustomKey) {
    ui.inputOpenAICustomKey.value = openKey;
  }
  const gKey = localStorage.getItem("khmerdub_google_api_key");
  if (gKey && ui.inputGoogleCustomKey) {
    ui.inputGoogleCustomKey.value = gKey;
  }

  // Restore cached AI Settings immediately on startup so refresh never clears the UI
  const savedAi = localStorage.getItem("khmerdub_ai_settings");
  if (savedAi) {
    try {
      const parsedAi = JSON.parse(savedAi);
      applyAiSettingsToUI(parsedAi);
    } catch (e) { }
  }
  updateAllProviderStatusBadges();

  // Restore Dubbing Speed Mode
  const savedDubMode = localStorage.getItem("dubstudio_dubbing_mode") || "fast";
  setDubbingMode(savedDubMode);
  bindDubbingModeEvents();
}

async function checkServerConfig() {
  try {
    const res = await fetch("/api/config");
    if (res.ok) {
      const data = await res.json();
      appState.hasServerApiKey = data.has_server_gemini_key;
      if (appState.hasServerApiKey) {
        ui.keyIconDot.classList.add("active");
      }
      if (data.translation_providers && Array.isArray(data.translation_providers)) {
        appState.translationEngine.providers = data.translation_providers;
        populateProjectProviderDropdown(data.translation_providers);
      }
      if (data.translation_settings) {
        applyAiSettingsToUI(data.translation_settings);
      }
    }
  } catch (err) {
    console.warn("Could not check server config:", err);
  }
}

// Modals Management
function openExportModal() {
  const modal = ui.exportModal || document.getElementById("exportModal");
  if (modal) modal.classList.remove("hidden");
}
function closeExportModal() {
  const modal = ui.exportModal || document.getElementById("exportModal");
  if (modal) modal.classList.add("hidden");
}

function openApiKeyModal() {
  const modal = ui.apiKeyModal || document.getElementById("apiKeyModal");
  if (modal) {
    modal.classList.remove("hidden");
    if (ui.inputGeminiKey) ui.inputGeminiKey.focus();
  }
}
function closeApiKeyModal() {
  const modal = ui.apiKeyModal || document.getElementById("apiKeyModal");
  if (modal) modal.classList.add("hidden");
}

window.openExportModal = openExportModal;
window.closeExportModal = closeExportModal;
window.openApiKeyModal = openApiKeyModal;
window.closeApiKeyModal = closeApiKeyModal;

// Blur Studio Dialog
function openBlurStudioDialog() {
  const modal = document.getElementById("blurStudioModal");
  if (modal) {
    modal.classList.remove("hidden");
    // Small entrance animation trigger
    requestAnimationFrame(() => {
      const dialog = modal.querySelector(".blur-studio-dialog");
      if (dialog) dialog.classList.add("dialog-visible");
    });
  }
}
function closeBlurStudioDialog() {
  const modal = document.getElementById("blurStudioModal");
  if (!modal) return;
  const dialog = modal.querySelector(".blur-studio-dialog");
  if (dialog) {
    dialog.classList.remove("dialog-visible");
    dialog.classList.add("dialog-closing");
    setTimeout(() => {
      modal.classList.add("hidden");
      dialog.classList.remove("dialog-closing");
    }, 220);
  } else {
    modal.classList.add("hidden");
  }
}
window.openBlurStudioDialog = openBlurStudioDialog;
window.closeBlurStudioDialog = closeBlurStudioDialog;

// Subtitle Studio Glass Dialog Modal
function openSubtitleStudioDialog() {
  const modal = document.getElementById("subtitleStudioModal");
  if (modal) {
    const modalBody = document.getElementById("subtitleStudioModalBodyContent");
    const subpanel = document.getElementById("subpanelSubtitleStudio");
    if (modalBody && subpanel && subpanel.parentElement !== modalBody) {
      modalBody.appendChild(subpanel);
    }
    if (subpanel) {
      subpanel.classList.remove("hidden");
      subpanel.style.display = "flex";
    }

    modal.classList.remove("hidden");
    requestAnimationFrame(() => {
      const dialog = modal.querySelector(".blur-studio-dialog");
      if (dialog) dialog.classList.add("dialog-visible");
    });
  }
}

function closeSubtitleStudioDialog() {
  const modal = document.getElementById("subtitleStudioModal");
  if (!modal) return;
  const dialog = modal.querySelector(".blur-studio-dialog");
  if (dialog) {
    dialog.classList.remove("dialog-visible");
    dialog.classList.add("dialog-closing");
    setTimeout(() => {
      modal.classList.add("hidden");
      dialog.classList.remove("dialog-closing");
      if (appState.activeStudioTab === "subtitles") {
        switchStudioTab("voice");
      }
    }, 220);
  } else {
    modal.classList.add("hidden");
    if (appState.activeStudioTab === "subtitles") {
      switchStudioTab("voice");
    }
  }
}
window.openSubtitleStudioDialog = openSubtitleStudioDialog;
window.closeSubtitleStudioDialog = closeSubtitleStudioDialog;

// Story Recap Glass Dialog Modal
function openRecapStudioDialog() {
  const modal = document.getElementById("recapStudioModal");
  if (modal) {
    const modalBody = document.getElementById("recapStudioModalBodyContent");
    const subpanel = document.getElementById("subpanelRecapStudio");
    if (modalBody && subpanel && subpanel.parentElement !== modalBody) {
      modalBody.appendChild(subpanel);
    }
    if (subpanel) {
      subpanel.classList.remove("hidden");
      subpanel.style.display = "flex";
    }

    modal.classList.remove("hidden");
    requestAnimationFrame(() => {
      const dialog = modal.querySelector(".blur-studio-dialog");
      if (dialog) dialog.classList.add("dialog-visible");
    });
  }
}

function closeRecapStudioDialog() {
  const modal = document.getElementById("recapStudioModal");
  if (!modal) return;
  const dialog = modal.querySelector(".blur-studio-dialog");
  if (dialog) {
    dialog.classList.remove("dialog-visible");
    dialog.classList.add("dialog-closing");
    setTimeout(() => {
      modal.classList.add("hidden");
      dialog.classList.remove("dialog-closing");
      if (appState.activeStudioTab === "recap") {
        switchStudioTab("voice");
      }
    }, 220);
  } else {
    modal.classList.add("hidden");
    if (appState.activeStudioTab === "recap") {
      switchStudioTab("voice");
    }
  }
}
window.openRecapStudioDialog = openRecapStudioDialog;
window.closeRecapStudioDialog = closeRecapStudioDialog;

async function saveGeminiApiKey() {
  const input = ui.inputGeminiKey || document.getElementById("inputGeminiKey");
  const key = input ? input.value.trim() : "";
  if (key) {
    localStorage.setItem("khmerdub_gemini_api_key", key);
    appState.geminiApiKey = key;
    if (ui.inputGeminiCustomKey) ui.inputGeminiCustomKey.value = key;
    if (ui.keyIconDot) ui.keyIconDot.classList.add("active");
    try {
      await fetch("/api/settings/save-gemini-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key })
      });
      await fetch("/api/translation/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: "gemini",
          credentials: { gemini_api_key: key, api_key: key }
        })
      });
    } catch (e) {
      console.warn("Could not sync key to server:", e);
    }
    showToast("Gemini API Key Saved Forever & Connected!");
    closeApiKeyModal();
  } else {
    const existing = localStorage.getItem("khmerdub_gemini_api_key") || appState.geminiApiKey;
    if (existing) {
      showToast("Existing saved Gemini Key retained.");
      closeApiKeyModal();
    } else {
      showToast("Please enter a valid Gemini API key.");
    }
  }
}

// ==========================================================================
// Utilities
// ==========================================================================
function formatTimecodeSimple(seconds) {
  if (isNaN(seconds) || seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function formatTimecodePrecise(seconds) {
  if (isNaN(seconds) || seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(2);
  const parts = s.split(".");
  return `${m.toString().padStart(2, "0")}:${parts[0].padStart(2, "0")}.${parts[1]}`;
}

function parseTimecode(str) {
  if (!str) return 0;
  const clean = str.replace(",", ".");
  const parts = clean.split(":");
  if (parts.length === 2) {
    return parseFloat(parts[0]) * 60 + parseFloat(parts[1]);
  } else if (parts.length === 3) {
    return parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2]);
  }
  return parseFloat(str) || 0;
}

function escapeHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast(msg) {
  const toast = document.createElement("div");
  toast.className = "toast-msg";
  toast.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <path d="M20 6L9 17l-5-5"/>
    </svg>
    <span>${escapeHtml(msg)}</span>
  `;
  ui.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.25s ease";
    setTimeout(() => toast.remove(), 250);
  }, 2800);
}

// ==========================================================================
// 6. Side-by-Side Floating Resizable Split Layout & Voice Sample Player
// ==========================================================================
function bindStudioSplitLayoutEvents() {
  const btnToggleSplit = document.getElementById("btnToggleSplitLayout");
  const container = document.querySelector(".workspace-left-column");
  const resizer = document.getElementById("studioSplitResizer");

  if (!btnToggleSplit || !container) return;

  // Restore user saved preferences
  try {
    const savedMode = localStorage.getItem("dubstudio_split_layout");
    const savedWidth = localStorage.getItem("dubstudio_split_width");
    if (savedWidth) {
      container.style.setProperty("--split-video-width", `${savedWidth}%`);
    }
    if (savedMode === "side-by-side") {
      container.classList.add("side-by-side-layout");
      btnToggleSplit.classList.add("active-split");
      btnToggleSplit.title = "Switch to Stacked Layout (ប្តូរទៅផ្ទាំងជាន់លើគ្នា)";
    }
  } catch (e) {
    console.warn("Could not read split layout preference:", e);
  }

  btnToggleSplit.addEventListener("click", () => {
    const isSide = container.classList.toggle("side-by-side-layout");
    btnToggleSplit.classList.toggle("active-split", isSide);
    btnToggleSplit.title = isSide
      ? "Switch to Stacked Layout (ប្តូរទៅផ្ទាំងជាន់លើគ្នា)"
      : "Side-by-Side Floating Split View (ពង្រីកផ្ទាំងទន្ទឹមគ្នា)";
    try {
      localStorage.setItem("dubstudio_split_layout", isSide ? "side-by-side" : "stacked");
    } catch (e) { }
    showToast(isSide ? "Side-by-Side Split View Enabled" : "Stacked Layout Enabled");
    if (typeof syncOverlayToVideo === "function") {
      setTimeout(syncOverlayToVideo, 50);
    }
  });

  if (resizer) {
    let isDragging = false;
    let startX = 0;
    let initialContainerWidth = 0;

    resizer.addEventListener("mousedown", (e) => {
      if (!container.classList.contains("side-by-side-layout")) return;
      isDragging = true;
      startX = e.clientX;
      initialContainerWidth = container.getBoundingClientRect().width;
      resizer.classList.add("is-dragging");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      e.preventDefault();
    });

    window.addEventListener("mousemove", (e) => {
      if (!isDragging || !initialContainerWidth) return;
      const rect = container.getBoundingClientRect();
      const relativeX = e.clientX - rect.left;
      let pct = (relativeX / rect.width) * 100;
      pct = Math.max(25, Math.min(75, pct));
      container.style.setProperty("--split-video-width", `${pct.toFixed(1)}%`);
      try {
        localStorage.setItem("dubstudio_split_width", pct.toFixed(1));
      } catch (e) { }
    });

    window.addEventListener("mouseup", () => {
      if (isDragging) {
        isDragging = false;
        resizer.classList.remove("is-dragging");
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        if (typeof syncOverlayToVideo === "function") {
          setTimeout(syncOverlayToVideo, 50);
        }
      }
    });
  }
}

function bindVoiceSampleEvents() {
  const btnVoiceSample = document.getElementById("btnPlayVoiceSample");
  const selectVoice = document.getElementById("selectVoiceModel");
  if (!btnVoiceSample || !selectVoice) return;

  btnVoiceSample.addEventListener("click", async () => {
    const selectedVoiceVal = selectVoice.value || "km-KH-PisethNeural";
    const sampleText = selectedVoiceVal.includes("Sreymom")
      ? "សួស្តី! ខ្ញុំជាសំឡេងស្រីឆ្លាតវៃ AI សម្រាប់បញ្ចូលសំឡេងភាពយន្ត។"
      : "សួស្តី! ខ្ញុំជាសំឡេងប្រុសឆ្លាតវៃ AI សម្រាប់បញ្ចូលសំឡេងភាពយន្ត។";

    btnVoiceSample.classList.add("loading");
    btnVoiceSample.disabled = true;

    try {
      const res = await fetch("/api/tts/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: sampleText,
          voice: selectedVoiceVal,
          rate: typeof getVoiceRateString === "function" ? getVoiceRateString() : "+0%",
          pitch: typeof getVoicePitchString === "function" ? getVoicePitchString() : "+0Hz",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const sampleAudio = new Audio(data.audio_url);
        btnVoiceSample.classList.remove("loading");
        btnVoiceSample.classList.add("playing");

        sampleAudio.onended = () => {
          btnVoiceSample.classList.remove("playing");
          btnVoiceSample.disabled = false;
        };
        sampleAudio.onerror = () => {
          btnVoiceSample.classList.remove("playing");
          btnVoiceSample.disabled = false;
          showToast("Error playing sample audio");
        };
        await sampleAudio.play();
      } else {
        throw new Error("Failed to generate voice audition");
      }
    } catch (err) {
      console.warn("Voice sample audition error:", err);
      btnVoiceSample.classList.remove("loading", "playing");
      btnVoiceSample.disabled = false;
      showToast("Could not play voice preview");
    }
  });
}

// ==========================================================================
// Timeline Validation Global Helpers
// ==========================================================================

function validateAndMarkSubtitle(sub) {
  const v = TimelineValidator.validateSubtitle(sub, appState.duration, appState.subtitles);
  sub._validationState = v;
  return v;
}

function runTimelineValidation() {
  if (appState.subtitles) appState.subtitles.forEach(sub => validateAndMarkSubtitle(sub));
  renderSubtitlesTable();
  renderTimelineBlocks();
  updateStatusMetrics();
}

window.autoFixTimeline = function (id, event) {
  if (event) event.stopPropagation();
  const sub = appState.subtitles.find(s => s.id === id);
  if (!sub) return;
  const v = TimelineValidator.validateSubtitle(sub, appState.duration, appState.subtitles);
  let fixed = false;
  if (v.overflow) {
    TimelineValidator.autoFixOverflow(sub, appState.duration);
    showToast('Fixed overflow: Subtitle #' + id + ' end clamped to ' + formatTimecodePrecise(appState.duration));
    fixed = true;
  }
  if (v.collision && v.collisionWith) {
    const colId = typeof v.collisionWith === "object" ? v.collisionWith.id : v.collisionWith;
    const targetSub = appState.subtitles.find(s => s.id === colId) || v.collisionWith;
    const aStart = parseFloat(sub.start) || 0;
    const bStart = parseFloat(targetSub.start) || 0;
    const earlier = aStart <= bStart ? sub : targetSub;
    const later = aStart <= bStart ? targetSub : sub;
    TimelineValidator.autoFixCollision(earlier, later);
    showToast('Fixed collision between subtitle #' + earlier.id + ' and #' + later.id);
    fixed = true;
  }
  if (!fixed) showToast('Subtitle #' + id + ' has no fixable issue');
  pushSubtitleHistory('Auto fix timeline issue');
  renderSubtitlesTable();
  renderTimelineBlocks();
};

window.undoTimelineFix = function (id, event) {
  if (event) event.stopPropagation();
  const sub = appState.subtitles.find(s => s.id === id);
  if (!sub) return;
  TimelineValidator.undoFix(sub);
  pushSubtitleHistory('Undo timeline fix');
  renderSubtitlesTable();
  renderTimelineBlocks();
  showToast('Subtitle #' + id + ' timestamps restored');
};

window.autoFixAllTimeline = function () {
  if (!appState.subtitles || appState.duration <= 0) return;
  TimelineValidator.autoFixAll(appState.subtitles, appState.duration);
  pushSubtitleHistory('Auto fix all timeline issues');
  renderSubtitlesTable();
  renderTimelineBlocks();
  showToast('All timeline issues auto-fixed');
  const modal = document.getElementById('timelineErrorModal');
  if (modal) modal.remove();
};

function showTimelineErrorModal(blockers) {
  const existing = document.getElementById('timelineErrorModal');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'timelineErrorModal';
  modal.className = 'timeline-error-modal-overlay';

  const issuesList = blockers.map(function (b) {
    var amt = b.overflowAmt > 0
      ? ' — extends +' + b.overflowAmt.toFixed(2) + 's past video end'
      : b.collisionAmt > 0
        ? ' — overlaps ' + b.collisionAmt.toFixed(2) + 's with #' + (b.collisionWith ? b.collisionWith.id : '?')
        : '';
    var icon = b.overflow ? 'OVERFLOW' : b.collision ? 'COLLISION' : 'INVALID';
    return '<li class="timeline-err-item"><span class="err-type-badge">' + icon + '</span> Subtitle <strong>#' + b.sub.id + '</strong>: ' + formatTimecodePrecise(b.sub.start) + ' to ' + formatTimecodePrecise(b.sub.end) + amt + '</li>';
  }).join('');

  modal.innerHTML = '<div class="timeline-error-modal-box">' +
    '<div class="timeline-error-modal-header">' +
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2">' +
    '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>' +
    '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' +
    '<h3>Cannot Export &mdash; Timeline Issues Detected</h3></div>' +
    '<p class="timeline-err-desc">Resolve all critical issues before generating the final dubbed video.</p>' +
    '<ul class="timeline-err-list">' + issuesList + '</ul>' +
    '<div class="timeline-error-modal-actions">' +
    '<button class="btn-fix-all-issues" onclick="autoFixAllTimeline()">Auto Fix All</button>' +
    '<button class="btn-review-issues" onclick="document.getElementById(\'timelineErrorModal\').remove();renderSubtitlesTable();">Review Issues</button>' +
    '<button class="btn-dismiss-modal" onclick="document.getElementById(\'timelineErrorModal\').remove()">Dismiss</button>' +
    '</div></div>';

  modal.addEventListener('click', function (e) { if (e.target === modal) modal.remove(); });
  document.body.appendChild(modal);
}

window.addEventListener("resize", () => {
  if (typeof syncOverlayToVideo === "function") syncOverlayToVideo();
  if (typeof updateBlurPreview === "function") updateBlurPreview(appState.currentTime);
});

// ==========================================================================
// Multi-Project Batch Translation Module
// ==========================================================================
let batchAvailableProjects = [];
let batchSelectedProjectIds = new Set();
let batchPollTimer = null;
let currentActiveBatchId = null;

function initBatchTranslation() {
  const btnTrigger = document.getElementById("btnBatchTranslateTrigger");
  const btnSidebar = document.getElementById("btnSidebarBatchTranslate");
  const modal = document.getElementById("modalBatchTranslate");
  const btnClose = document.getElementById("btnCloseBatchModal");
  const btnCancel = document.getElementById("btnCancelBatchModal");
  const btnStart = document.getElementById("btnStartBatchExecution");

  if (btnTrigger) btnTrigger.addEventListener("click", openBatchTranslateModal);
  if (btnSidebar) btnSidebar.addEventListener("click", openBatchTranslateModal);
  if (btnClose) btnClose.addEventListener("click", closeBatchTranslateModal);
  if (btnCancel) btnCancel.addEventListener("click", closeBatchTranslateModal);
  if (btnStart) btnStart.addEventListener("click", executeBatchTranslation);

  // Close on backdrop click
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeBatchTranslateModal();
    });
  }

  // Selection toolbar buttons
  const btnSelectAll = document.getElementById("btnBatchSelectAll");
  const btnSelectUntranslated = document.getElementById("btnBatchSelectUntranslated");
  const btnClear = document.getElementById("btnBatchClearSelection");
  const masterCheckbox = document.getElementById("batchMasterCheckbox");
  const searchInput = document.getElementById("batchProjectSearch");

  if (btnSelectAll) {
    btnSelectAll.addEventListener("click", () => {
      batchAvailableProjects.forEach(p => {
        if (p.total_segments > 0) batchSelectedProjectIds.add(p.project_id);
      });
      syncBatchCheckboxes();
      updateBatchSelectedCounter();
    });
  }

  if (btnSelectUntranslated) {
    btnSelectUntranslated.addEventListener("click", () => {
      batchSelectedProjectIds.clear();
      batchAvailableProjects.forEach(p => {
        if (p.total_segments > 0 && p.translation_status !== "completed") {
          batchSelectedProjectIds.add(p.project_id);
        }
      });
      syncBatchCheckboxes();
      updateBatchSelectedCounter();
    });
  }

  if (btnClear) {
    btnClear.addEventListener("click", () => {
      batchSelectedProjectIds.clear();
      syncBatchCheckboxes();
      updateBatchSelectedCounter();
    });
  }

  if (masterCheckbox) {
    masterCheckbox.addEventListener("change", (e) => {
      if (e.target.checked) {
        batchAvailableProjects.forEach(p => {
          if (p.total_segments > 0) batchSelectedProjectIds.add(p.project_id);
        });
      } else {
        batchSelectedProjectIds.clear();
      }
      syncBatchCheckboxes();
      updateBatchSelectedCounter();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      const rows = document.querySelectorAll("#batchProjectsTableBody tr");
      rows.forEach(r => {
        const name = r.getAttribute("data-name") || "";
        if (!q || name.toLowerCase().includes(q)) {
          r.style.display = "";
        } else {
          r.style.display = "none";
        }
      });
    });
  }

  // Floating progress card buttons
  const btnToggleCollapse = document.getElementById("btnToggleBatchCardCollapse");
  const btnCloseCard = document.getElementById("btnCloseBatchCard");
  const btnCancelBatch = document.getElementById("btnCancelActiveBatch");
  const btnRetryFailed = document.getElementById("btnRetryFailedBatch");

  if (btnToggleCollapse) {
    btnToggleCollapse.addEventListener("click", (e) => {
      e.stopPropagation();
      const card = document.getElementById("floatingBatchCard");
      if (card) card.classList.toggle("collapsed");
    });
  }

  const cardHeader = document.getElementById("batchCardHeader");
  if (cardHeader) {
    cardHeader.addEventListener("click", () => {
      const card = document.getElementById("floatingBatchCard");
      if (card) card.classList.toggle("collapsed");
    });
  }

  if (btnCloseCard) {
    btnCloseCard.addEventListener("click", (e) => {
      e.stopPropagation();
      const card = document.getElementById("floatingBatchCard");
      if (card) card.classList.add("hidden");
    });
  }

  if (btnCancelBatch) {
    btnCancelBatch.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!currentActiveBatchId) return;
      if (!confirm("Are you sure you want to cancel the active batch translation?")) return;
      try {
        await fetch(`/api/batch/${currentActiveBatchId}/cancel`, { method: "POST" });
        showToast("Batch translation cancelled.");
        if (batchPollTimer) clearInterval(batchPollTimer);
        pollBatchStatus(currentActiveBatchId);
      } catch (err) {
        showToast("Failed to cancel batch: " + err.message);
      }
    });
  }

  if (btnRetryFailed) {
    btnRetryFailed.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!currentActiveBatchId) return;
      try {
        const res = await fetch(`/api/batch/${currentActiveBatchId}/retry`, { method: "POST" });
        if (res.ok) {
          showToast("Retrying failed projects in batch...");
          btnRetryFailed.classList.add("hidden");
          startBatchPolling(currentActiveBatchId);
        }
      } catch (err) {
        showToast("Failed to retry batch: " + err.message);
      }
    });
  }

  // Check if a batch is already active on server startup
  checkActiveBatchOnLoad();
}

async function checkActiveBatchOnLoad() {
  try {
    const res = await fetch("/api/batch/active");
    if (!res.ok) return;
    const data = await res.json();
    if (data.success && data.batch) {
      const batch = data.batch;
      if (batch.status === "running" || batch.status === "pending") {
        currentActiveBatchId = batch.batch_id;
        showFloatingBatchCard();
        startBatchPolling(batch.batch_id);
      }
    }
  } catch (e) { }
}

async function openBatchTranslateModal() {
  const modal = document.getElementById("modalBatchTranslate");
  if (!modal) return;
  modal.classList.remove("hidden");

  const loadingEl = document.getElementById("batchProjectListLoading");
  const tableEl = document.getElementById("batchProjectsTable");
  const tbody = document.getElementById("batchProjectsTableBody");
  const searchInput = document.getElementById("batchProjectSearch");
  if (searchInput) searchInput.value = "";

  if (loadingEl) loadingEl.style.display = "block";
  if (tableEl) tableEl.style.display = "none";
  if (tbody) tbody.innerHTML = "";

  batchSelectedProjectIds.clear();
  updateBatchSelectedCounter();

  try {
    const res = await fetch("/api/projects");
    if (!res.ok) throw new Error("Failed to load projects list");
    const data = await res.json();
    batchAvailableProjects = data.projects || [];

    const totalEl = document.getElementById("batchTotalAvailable");
    if (totalEl) totalEl.textContent = batchAvailableProjects.length;

    renderBatchProjectsTable(batchAvailableProjects);

    // Auto-select untranslated projects by default if available
    let autoSelected = 0;
    batchAvailableProjects.forEach(p => {
      if (p.total_segments > 0 && p.translation_status !== "completed") {
        batchSelectedProjectIds.add(p.project_id);
        autoSelected++;
      }
    });

    // If all are completed, select all with segments
    if (autoSelected === 0) {
      batchAvailableProjects.forEach(p => {
        if (p.total_segments > 0) batchSelectedProjectIds.add(p.project_id);
      });
    }

    syncBatchCheckboxes();
    updateBatchSelectedCounter();

  } catch (err) {
    if (loadingEl) loadingEl.innerHTML = `<span style="color:#f87171;">Error loading projects: ${err.message}</span>`;
  }
}

function closeBatchTranslateModal() {
  const modal = document.getElementById("modalBatchTranslate");
  if (modal) modal.classList.add("hidden");
}

function renderBatchProjectsTable(projects) {
  const loadingEl = document.getElementById("batchProjectListLoading");
  const tableEl = document.getElementById("batchProjectsTable");
  const tbody = document.getElementById("batchProjectsTableBody");
  if (!tbody) return;

  if (loadingEl) loadingEl.style.display = "none";
  if (tableEl) tableEl.style.display = "table";

  if (projects.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#94a3b8;">No projects found on server yet. Upload and transcribe videos first.</td></tr>`;
    return;
  }

  tbody.innerHTML = projects.map(p => {
    const durStr = p.duration ? (typeof formatTimecodePrecise === "function" ? formatTimecodePrecise(p.duration).slice(0, 5) : `${Math.floor(p.duration / 60)}:${Math.floor(p.duration % 60).toString().padStart(2, '0')}`) : "--:--";
    const hasSubtitles = p.total_segments > 0;
    const isCurrent = (p.project_id === appState.sessionId);

    let statusBadge = "";
    if (!hasSubtitles) {
      statusBadge = `<span class="batch-status-badge empty" title="No subtitles transcribed yet">No Subtitles</span>`;
    } else if (p.translation_status === "completed") {
      statusBadge = `<span class="batch-status-badge completed" title="All subtitles translated to Khmer">Completed</span>`;
    } else if (p.translation_status === "partial") {
      statusBadge = `<span class="batch-status-badge partial" title="Partially translated">Partial (${p.translated_segments}/${p.total_segments})</span>`;
    } else {
      statusBadge = `<span class="batch-status-badge untranslated" title="Awaiting translation">Untranslated</span>`;
    }

    const subText = hasSubtitles
      ? `<span style="color:#cbd5e1;">${p.translated_segments} / ${p.total_segments}</span> <span style="font-size:10px; color:#64748b;">lines</span>`
      : `<span style="color:#ef4444; font-size:11px;">0 lines (run STT)</span>`;

    return `
      <tr data-id="${p.project_id}" data-name="${escapeHtml(p.filename)}" style="border-bottom: 1px solid rgba(255,255,255,0.05); cursor: ${hasSubtitles ? 'pointer' : 'not-allowed'}; opacity: ${hasSubtitles ? '1' : '0.6'};">
        <td style="padding: 9px 12px; text-align: center;">
          <input type="checkbox" class="batch-row-checkbox" data-id="${p.project_id}" ${!hasSubtitles ? 'disabled' : ''} />
        </td>
        <td style="padding: 9px 12px;">
          <div style="font-weight: 500; color: #f1f5f9; display: flex; align-items: center; gap: 6px;">
            <span>${escapeHtml(p.filename)}</span>
            ${isCurrent ? '<span style="font-size:9px; background:rgba(99,102,241,0.25); color:#a5b4fc; padding:1px 6px; border-radius:4px;">Current</span>' : ''}
          </div>
          <div style="font-size: 10.5px; color: #64748b; font-family: monospace;">${p.project_id}</div>
        </td>
        <td style="padding: 9px 12px; font-size: 11.5px; color: #94a3b8;">${durStr}</td>
        <td style="padding: 9px 12px; font-size: 11.5px;">${subText}</td>
        <td style="padding: 9px 12px;">${statusBadge}</td>
      </tr>
    `;
  }).join("");

  // Attach click listener on rows
  tbody.querySelectorAll("tr").forEach(tr => {
    tr.addEventListener("click", (e) => {
      if (e.target.tagName === "INPUT") return;
      const chk = tr.querySelector(".batch-row-checkbox");
      if (chk && !chk.disabled) {
        chk.checked = !chk.checked;
        const pid = chk.getAttribute("data-id");
        if (chk.checked) batchSelectedProjectIds.add(pid);
        else batchSelectedProjectIds.delete(pid);
        updateBatchSelectedCounter();
      }
    });
  });

  tbody.querySelectorAll(".batch-row-checkbox").forEach(chk => {
    chk.addEventListener("change", (e) => {
      const pid = e.target.getAttribute("data-id");
      if (e.target.checked) batchSelectedProjectIds.add(pid);
      else batchSelectedProjectIds.delete(pid);
      updateBatchSelectedCounter();
    });
  });
}

function syncBatchCheckboxes() {
  const checkboxes = document.querySelectorAll(".batch-row-checkbox");
  checkboxes.forEach(chk => {
    const pid = chk.getAttribute("data-id");
    if (!chk.disabled) {
      chk.checked = batchSelectedProjectIds.has(pid);
    }
  });

  const masterCheckbox = document.getElementById("batchMasterCheckbox");
  if (masterCheckbox) {
    const enabledCheckboxes = Array.from(checkboxes).filter(c => !c.disabled);
    masterCheckbox.checked = enabledCheckboxes.length > 0 && enabledCheckboxes.every(c => c.checked);
  }
}

function updateBatchSelectedCounter() {
  const count = batchSelectedProjectIds.size;
  const countEl = document.getElementById("batchSelectedCount");
  if (countEl) countEl.textContent = count;

  const btnStart = document.getElementById("btnStartBatchExecution");
  const labelEl = document.getElementById("btnStartBatchLabel");
  if (btnStart) {
    btnStart.disabled = (count === 0);
  }
  if (labelEl) {
    labelEl.textContent = `Start Batch Translation (${count} Project${count === 1 ? '' : 's'})`;
  }
}

async function executeBatchTranslation() {
  const pids = Array.from(batchSelectedProjectIds);
  if (pids.length === 0) {
    showToast("Please select at least one project to translate.");
    return;
  }

  const provider = document.getElementById("batchSelectProvider") ? document.getElementById("batchSelectProvider").value : "gemini";
  const style = document.getElementById("batchSelectStyle") ? document.getElementById("batchSelectStyle").value : "natural";
  const concurrency = document.getElementById("batchSelectConcurrency") ? parseInt(document.getElementById("batchSelectConcurrency").value, 10) : 2;
  const skipAlready = document.getElementById("batchChkSkipTranslated") ? document.getElementById("batchChkSkipTranslated").checked : true;
  const useGlossary = document.getElementById("batchChkUseGlossary") ? document.getElementById("batchChkUseGlossary").checked : true;

  const btnStart = document.getElementById("btnStartBatchExecution");
  if (btnStart) {
    btnStart.disabled = true;
    btnStart.innerHTML = `<div class="pulse-spinner-sm" style="display:inline-block; margin-right:6px;"></div> Starting batch...`;
  }

  try {
    const res = await fetch("/api/batch/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_ids: pids,
        provider,
        style,
        concurrency,
        skip_already_translated: skipAlready,
        options: {
          use_glossary: useGlossary,
          use_translation_memory: true,
          enable_fallback: true,
        },
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to start batch translation");
    }

    const data = await res.json();
    currentActiveBatchId = data.batch_id;

    closeBatchTranslateModal();
    showToast(`Batch translation started for ${data.total_projects} projects!`);

    showFloatingBatchCard();
    startBatchPolling(data.batch_id);

  } catch (err) {
    showToast("Error starting batch: " + err.message);
  } finally {
    if (btnStart) {
      btnStart.disabled = false;
      btnStart.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg><span id="btnStartBatchLabel">Start Batch Translation (${pids.length} Projects)</span>`;
    }
  }
}

function showFloatingBatchCard() {
  const card = document.getElementById("floatingBatchCard");
  if (card) {
    card.classList.remove("hidden");
    card.classList.remove("collapsed");
  }
}

function startBatchPolling(batchId) {
  if (batchPollTimer) clearInterval(batchPollTimer);
  currentActiveBatchId = batchId;

  // Initial poll
  pollBatchStatus(batchId);

  batchPollTimer = setInterval(() => {
    pollBatchStatus(batchId);
  }, 1500);
}

async function pollBatchStatus(batchId) {
  try {
    const res = await fetch(`/api/batch/${batchId}/status`);
    if (!res.ok) return;
    const data = await res.json();
    const batch = data.batch;
    if (!batch) return;

    renderBatchCardProgress(batch);

    if (["completed", "failed", "partial_error", "cancelled"].includes(batch.status)) {
      if (batchPollTimer) {
        clearInterval(batchPollTimer);
        batchPollTimer = null;
      }

      // Check if current active session was updated in batch
      if (appState.sessionId && batch.projects && batch.projects[appState.sessionId]) {
        const myProj = batch.projects[appState.sessionId];
        if (myProj.status === "completed") {
          // Refresh current project subtitles
          try {
            const sessRes = await fetch(`/api/session/${appState.sessionId}`);
            if (sessRes.ok) {
              const sessData = await sessRes.json();
              if (sessData.segments && sessData.segments.length > 0) {
                appState.subtitles = sessData.segments;
                renderSubtitlesTable();
                renderTimelineBlocks();
                showToast("Current project subtitles refreshed with translated text!");
              }
            }
          } catch (e) { }
        }
      }

      // Show toast on completion
      if (batch.status === "completed") {
        showToast(`🎉 Batch translation completed! (${batch.completed_projects}/${batch.total_projects} projects)`);
      } else if (batch.status === "partial_error") {
        showToast(`⚠️ Batch translation finished with errors (${batch.completed_projects} succeeded, ${batch.failed_projects} failed).`);
      } else if (batch.status === "failed") {
        showToast(`❌ Batch translation failed.`);
      }
    }
  } catch (e) { }
}

function renderBatchCardProgress(batch) {
  const card = document.getElementById("floatingBatchCard");
  if (!card) return;

  const spinner = document.getElementById("batchHeaderSpinner");
  const title = document.getElementById("batchCardTitle");
  const subtitle = document.getElementById("batchCardSubtitle");
  const fill = document.getElementById("batchOverallProgressFill");
  const itemsContainer = document.getElementById("batchCardItems");
  const btnRetry = document.getElementById("btnRetryFailedBatch");

  const total = batch.total_projects || 0;
  const completed = batch.completed_projects || 0;
  const failed = batch.failed_projects || 0;
  const pct = batch.overall_progress || 0;

  if (fill) fill.style.width = `${pct}%`;

  if (title) {
    if (batch.status === "running") {
      title.textContent = `Translating Projects (${pct}%)`;
    } else if (batch.status === "completed") {
      title.textContent = `Batch Completed ✅`;
    } else if (batch.status === "partial_error") {
      title.textContent = `Batch Finished (${failed} Failed)`;
    } else if (batch.status === "cancelled") {
      title.textContent = `Batch Cancelled ⏹️`;
    } else {
      title.textContent = `Batch Translation (${pct}%)`;
    }
  }

  if (subtitle) {
    subtitle.textContent = `${completed} / ${total} completed • Concurrency: ${batch.concurrency || 2}`;
  }

  if (spinner) {
    if (["running", "pending"].includes(batch.status)) {
      spinner.style.display = "block";
    } else {
      spinner.style.display = "none";
    }
  }

  if (btnRetry) {
    if (failed > 0 && ["partial_error", "failed"].includes(batch.status)) {
      btnRetry.classList.remove("hidden");
      btnRetry.textContent = `Retry ${failed} Failed`;
    } else {
      btnRetry.classList.add("hidden");
    }
  }

  // Render items
  if (itemsContainer && batch.projects) {
    const pList = Object.values(batch.projects);
    itemsContainer.innerHTML = pList.map(p => {
      let icon = "";
      let color = "#94a3b8";
      if (p.status === "translating") {
        icon = `<div class="pulse-spinner-sm" style="width:12px; height:12px; border-width:2px;"></div>`;
        color = "#60a5fa";
      } else if (p.status === "completed") {
        icon = `<span style="color:#10b981; font-weight:bold;">✓</span>`;
        color = "#34d399";
      } else if (p.status === "failed") {
        icon = `<span style="color:#ef4444; font-weight:bold;">✗</span>`;
        color = "#f87171";
      } else if (p.status === "skipped") {
        icon = `<span style="color:#64748b;">-</span>`;
      } else {
        icon = `<span style="color:#64748b; font-size:10px;">⏳</span>`;
      }

      return `
        <div class="batch-item-row" title="${escapeHtml(p.status_message || '')}">
          <div style="display:flex; align-items:center; gap:6px;">
            ${icon}
            <span class="batch-item-name">${escapeHtml(p.name)}</span>
          </div>
          <div style="font-size:10.5px; color:${color}; text-align:right;">
            ${p.status === "translating" ? `${p.progress}%` : p.status}
          </div>
        </div>
      `;
    }).join("");
  }
}

// ==========================================================================
// Projects Library & Tab Management Module (Tap Project)
// ==========================================================================
let allLibraryProjects = [];
let activeProjectsFilter = "all";

function initProjectsTab() {
  const btnNavEditor = document.getElementById("btnNavEditor");
  const btnNavProjects = document.getElementById("btnNavProjects");
  const btnUploadNew = document.getElementById("btnProjectsTabUploadNew");
  const btnBatch = document.getElementById("btnProjectsTabBatchTranslate");
  const btnRefresh = document.getElementById("btnRefreshProjectsList");
  const searchInput = document.getElementById("inputProjectsSearch");
  const btnClearSearch = document.getElementById("btnClearProjectsSearch");
  const filterPills = document.querySelectorAll("#projectsFilterPills .filter-pill");

  if (btnNavEditor) {
    btnNavEditor.addEventListener("click", () => switchMainDashboardView("editor"));
  }
  if (btnNavProjects) {
    btnNavProjects.addEventListener("click", () => switchMainDashboardView("projects"));
  }

  if (btnUploadNew) {
    btnUploadNew.addEventListener("click", () => {
      switchMainDashboardView("editor");
      if (ui.hiddenVideoUpload) ui.hiddenVideoUpload.click();
    });
  }

  if (btnBatch) {
    btnBatch.addEventListener("click", openBatchTranslateModal);
  }

  if (btnRefresh) {
    btnRefresh.addEventListener("click", loadProjectsLibrary);
  }

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const q = e.target.value.trim();
      if (btnClearSearch) {
        if (q) btnClearSearch.classList.remove("hidden");
        else btnClearSearch.classList.add("hidden");
      }
      renderFilteredProjectsGrid();
    });
  }

  if (btnClearSearch) {
    btnClearSearch.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      btnClearSearch.classList.add("hidden");
      renderFilteredProjectsGrid();
    });
  }

  filterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeProjectsFilter = pill.getAttribute("data-filter") || "all";
      renderFilteredProjectsGrid();
    });
  });

  // Load project counts for header badge initially
  fetchInitialProjectsCount();
}

function switchMainDashboardView(viewName) {
  const editorView = document.getElementById("editorWorkspaceContainer");
  const projectsView = document.getElementById("projectsDashboardContainer");
  const btnNavEditor = document.getElementById("btnNavEditor");
  const btnNavProjects = document.getElementById("btnNavProjects");

  if (viewName === "projects") {
    if (editorView) editorView.classList.add("hidden");
    if (projectsView) projectsView.classList.remove("hidden");
    if (btnNavEditor) btnNavEditor.classList.remove("active");
    if (btnNavProjects) btnNavProjects.classList.add("active");
    loadProjectsLibrary();
  } else {
    if (projectsView) projectsView.classList.add("hidden");
    if (editorView) editorView.classList.remove("hidden");
    if (btnNavProjects) btnNavProjects.classList.remove("active");
    if (btnNavEditor) btnNavEditor.classList.add("active");
  }
}

async function fetchInitialProjectsCount() {
  try {
    const res = await fetch("/api/projects");
    if (!res.ok) return;
    const data = await res.json();
    const count = (data.projects || []).length;
    const badge = document.getElementById("headerProjectsCountBadge");
    if (badge) badge.textContent = count;
  } catch (e) { }
}

async function loadProjectsLibrary() {
  const grid = document.getElementById("projectsLibraryGrid");
  if (!grid) return;

  grid.innerHTML = `
    <div class="projects-loading-state" id="projectsLoadingState">
      <div class="pulse-spinner-sm" style="margin: 0 auto 12px; width: 24px; height: 24px;"></div>
      <span>Loading projects library...</span>
    </div>
  `;

  try {
    const res = await fetch("/api/projects");
    if (!res.ok) throw new Error("Failed to load projects");
    const data = await res.json();
    allLibraryProjects = data.projects || [];

    // Update counts
    const totalCount = allLibraryProjects.length;
    const untranslatedCount = allLibraryProjects.filter(p => p.translation_status !== "completed").length;
    const completedCount = allLibraryProjects.filter(p => p.translation_status === "completed").length;
    const hasSubsCount = allLibraryProjects.filter(p => p.total_segments > 0).length;

    const countAll = document.getElementById("countAllProjects");
    const countUntrans = document.getElementById("countUntranslatedProjects");
    const countComp = document.getElementById("countCompletedProjects");
    const countSubs = document.getElementById("countHasSubsProjects");
    const headerBadge = document.getElementById("headerProjectsCountBadge");

    if (countAll) countAll.textContent = totalCount;
    if (countUntrans) countUntrans.textContent = untranslatedCount;
    if (countComp) countComp.textContent = completedCount;
    if (countSubs) countSubs.textContent = hasSubsCount;
    if (headerBadge) headerBadge.textContent = totalCount;

    renderFilteredProjectsGrid();

  } catch (err) {
    grid.innerHTML = `
      <div class="projects-empty-state">
        <span style="color:#f87171;">Failed to load projects: ${escapeHtml(err.message)}</span>
      </div>
    `;
  }
}

function renderFilteredProjectsGrid() {
  const grid = document.getElementById("projectsLibraryGrid");
  const searchInput = document.getElementById("inputProjectsSearch");
  if (!grid) return;

  const q = searchInput ? searchInput.value.toLowerCase().trim() : "";

  let filtered = allLibraryProjects.filter(p => {
    // Search query
    if (q) {
      const matchName = (p.filename || "").toLowerCase().includes(q);
      const matchId = (p.project_id || "").toLowerCase().includes(q);
      if (!matchName && !matchId) return false;
    }

    // Filter pill
    if (activeProjectsFilter === "untranslated") {
      return p.translation_status !== "completed";
    }
    if (activeProjectsFilter === "completed") {
      return p.translation_status === "completed";
    }
    if (activeProjectsFilter === "has_subs") {
      return p.total_segments > 0;
    }
    return true;
  });

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="projects-empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="1.5" style="margin:0 auto 12px;">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
        <p style="font-weight:600; color:#cbd5e1; margin-bottom:4px;">No projects found</p>
        <span style="font-size:12px; color:#64748b;">${q ? 'Try matching another search term.' : 'Click "New Video Project" to start dubbing.'}</span>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(p => {
    const isCurrent = (p.project_id === appState.sessionId);
    const durStr = p.duration ? (typeof formatTimecodePrecise === "function" ? formatTimecodePrecise(p.duration).slice(0, 5) : `${Math.floor(p.duration / 60)}:${Math.floor(p.duration % 60).toString().padStart(2, '0')}`) : "--:--";
    const totalSegs = p.total_segments || 0;
    const transSegs = p.translated_segments || 0;
    const pct = totalSegs > 0 ? Math.round((transSegs / totalSegs) * 100) : 0;

    let statusBadge = "";
    if (totalSegs === 0) {
      statusBadge = `<span class="batch-status-badge empty">No Subtitles</span>`;
    } else if (p.translation_status === "completed") {
      statusBadge = `<span class="batch-status-badge completed">Completed</span>`;
    } else if (p.translation_status === "partial") {
      statusBadge = `<span class="batch-status-badge partial">Partial (${pct}%)</span>`;
    } else {
      statusBadge = `<span class="batch-status-badge untranslated">Untranslated</span>`;
    }

    return `
      <div class="project-card ${isCurrent ? 'active-project' : ''}" data-project-id="${p.project_id}">
        <div class="project-card-banner">
          <div class="project-card-meta-tag">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            <span>${durStr}</span>
          </div>
          <div>${statusBadge}</div>
        </div>

        <div class="project-card-body">
          <div class="project-card-title" title="${escapeHtml(p.filename)}">
            ${isCurrent ? '<span style="color:#34d399; font-size:11px;">●</span>' : ''}
            <span>${escapeHtml(p.filename)}</span>
          </div>

          <div class="project-card-substats">
            <span>Subtitles: <strong>${transSegs} / ${totalSegs}</strong></span>
            <span>${pct}% Translated</span>
          </div>

          <div class="project-card-progress-bar">
            <div class="project-card-progress-fill" style="width: ${pct}%;"></div>
          </div>
        </div>

        <div class="project-card-footer">
          <button type="button" class="btn-card-open" onclick="openProjectInStudio('${p.project_id}')" title="Open this project in Studio Editor">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            <span>${isCurrent ? 'Current Project' : 'Open in Studio'}</span>
          </button>

          <button type="button" class="btn-card-del" onclick="deleteProjectFromLibrary('${p.project_id}', '${escapeHtml(p.filename).replace(/'/g, "\\'")}')" title="Delete project">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
      </div>
    `;
  }).join("");
}

window.openProjectInStudio = async function(projectId) {
  showPlayerLoading("Opening project into studio...");
  try {
    const res = await fetch(`/api/session/${projectId}`);
    if (!res.ok) throw new Error("Could not load project session data");
    const data = await res.json();

    appState.sessionId = data.session_id;
    appState.duration = (data.media_info && data.media_info.duration) || 0.0;
    appState.subtitles = data.segments || [];
    appState.projectName = data.original_filename || data.session_id;

    if (ui.inputProjectName) ui.inputProjectName.value = appState.projectName;
    if (ui.videoFilenameDisplay) ui.videoFilenameDisplay.textContent = appState.projectName;

    if (data.video_url) {
      ui.mainVideoPlayer.src = data.video_url;
      appState.videoUrl = data.video_url;
      if (ui.playerEmptyDropzone) ui.playerEmptyDropzone.classList.add("hidden");
      if (ui.mainVideoPlayer) ui.mainVideoPlayer.classList.remove("hidden");
    }

    setTimecodeDisplay(0, appState.duration);
    updateTimelineRuler(appState.duration);
    renderSubtitlesTable();
    renderTimelineBlocks();
    updateStatusMetrics();

    switchMainDashboardView("editor");
    showToast(`Project "${appState.projectName}" loaded! (${appState.subtitles.length} subtitles)`);

  } catch (err) {
    showToast("Error opening project: " + err.message);
  } finally {
    hidePlayerLoading();
  }
};

window.deleteProjectFromLibrary = async function(projectId, filename) {
  if (!confirm(`Are you sure you want to delete project "${filename}"?`)) return;
  try {
    const res = await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete project");
    showToast(`Deleted "${filename}".`);
    if (appState.sessionId === projectId) {
      appState.sessionId = null;
      appState.subtitles = [];
      renderSubtitlesTable();
      renderTimelineBlocks();
    }
    loadProjectsLibrary();
  } catch (err) {
    showToast("Error: " + err.message);
  }
};

// Start application
window.addEventListener("DOMContentLoaded", initDashboard);
