"use client";

import {
  DragEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  ChevronLeft,
  Download,
  Eye,
  FileText,
  FileUp,
  Folder,
  FolderPlus,
  Library,
  LoaderCircle,
  Play,
  Sparkles,
  Send,
  Trash2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { DocumentFolder, DocumentItem, StudyArtifact } from "@/types/api";
import { Button } from "@/components/ui/button";
import { StudyRibbon } from "@/components/study-ribbon";
import {
  ConfirmDialog,
  type ConfirmDialogState,
} from "@/components/confirm-dialog";

const types = [
  {
    value: "summary",
    label: "Summary",
    description: "A faithful overview of the material",
  },
  {
    value: "key_points",
    label: "Key points",
    description: "Essential facts at a glance",
  },
  {
    value: "short_notes",
    label: "Revision notes",
    description: "Concise notes for quick review",
  },
  {
    value: "explanation",
    label: "Clear explanation",
    description: "A guided, easy-to-follow lesson",
  },
  {
    value: "quiz",
    label: "Practice questions",
    description: "Questions, answers, and explanations",
  },
  {
    value: "flashcards",
    label: "Flashcards",
    description: "Active-recall revision cards",
  },
  {
    value: "true_false",
    label: "True or false",
    description: "Fast comprehension checks",
  },
  {
    value: "fill_blanks",
    label: "Fill in the blanks",
    description: "Memory and terminology practice",
  },
  {
    value: "concept_map",
    label: "Concept map",
    description: "Ideas organized by relationship",
  },
  {
    value: "study_plan",
    label: "Study plan",
    description: "A practical revision schedule",
  },
  {
    value: "essay_outline",
    label: "Essay outline",
    description: "Arguments, evidence, and structure",
  },
  {
    value: "vocabulary",
    label: "Vocabulary",
    description: "Important terms and definitions",
  },
  {
    value: "synonyms",
    label: "Synonyms",
    description: "Alternative words in context",
  },
  {
    value: "translation",
    label: "Translation",
    description: "English or Kinyarwanda meaning",
  },
];
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function StudyPage() {
  const token = useAuthStore((state) => state.accessToken)!,
    queryClient = useQueryClient(),
    fileInput = useRef<HTMLInputElement>(null);
  const [selectedTypes, setSelectedTypes] = useState<string[]>(["summary"]),
    [text, setText] = useState(""),
    [documentId, setDocumentId] = useState(""),
    [language, setLanguage] = useState("en"),
    [difficulty, setDifficulty] = useState("intermediate"),
    [length, setLength] = useState("medium"),
    [count, setCount] = useState(5),
    [voiceId, setVoiceId] = useState(""),
    [audioUrl, setAudioUrl] = useState<string | null>(null),
    [active, setActive] = useState<StudyArtifact | null>(null),
    [recentResults, setRecentResults] = useState<StudyArtifact[]>([]),
    [notice, setNotice] = useState(""),
    [documentQuestion, setDocumentQuestion] = useState(""),
    [documentAnswer, setDocumentAnswer] = useState(""),
    [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(
      null,
    );
  const [folderId, setFolderId] = useState(""),
    [folderName, setFolderName] = useState(""),
    [draggedDocumentId, setDraggedDocumentId] = useState(""),
    [dropTarget, setDropTarget] = useState<string | null>(null);
  const documents = useQuery({
    queryKey: ["documents", "study"],
    queryFn: () => api.documents(token),
  });
  const folders = useQuery({
    queryKey: ["document-folders"],
    queryFn: () => api.documentFolders(token),
  });
  const voices = useQuery({
    queryKey: ["voice-profiles"],
    queryFn: () => api.voiceProfiles(token),
  });
  const library = useQuery({
    queryKey: ["study-artifacts"],
    queryFn: () => api.studyArtifacts(token),
  });
  const documentPreview = useQuery({
    queryKey: ["document-content", documentId],
    queryFn: () => api.documentContent(documentId, token),
    enabled: Boolean(documentId),
  });
  const generate = useMutation({
    mutationFn: async () => {
      const created: StudyArtifact[] = [],
        failures: string[] = [];
      for (const artifactType of selectedTypes) {
        try {
          created.push(
            await api.generateStudy(
              {
                artifact_type: artifactType,
                text: text.trim() || null,
                document_id: documentId || null,
                language,
                difficulty,
                audience: "student",
                length,
                count,
              },
              token,
            ),
          );
        } catch (error) {
          failures.push(
            `${artifactType.replaceAll("_", " ")}: ${error instanceof Error ? error.message : "could not be created"}`,
          );
        }
      }
      return { created, failures };
    },
    onSuccess: ({ created, failures }) => {
      setActive(created[0] || null);
      setRecentResults(created);
      setNotice(
        created.length
          ? `${created.length} study ${created.length === 1 ? "item" : "items"} created and saved.${failures.length ? ` ${failures.length} could not be created.` : ""}`
          : `EVA could not create the selected items. ${failures[0] || "Please try again."}`,
      );
      queryClient.invalidateQueries({ queryKey: ["study-artifacts"] });
    },
  });
  const askDocument = useMutation({
    mutationFn: () =>
      api.askDocument(documentQuestion.trim(), documentId, token),
    onSuccess: (result) => {
      setDocumentAnswer(result.answer);
      setDocumentQuestion("");
    },
  });
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const result = await api.uploadDocument(file, token, folderId || null);
      setNotice(`Processing and classifying ${file.name}…`);
      for (let i = 0; i < 120; i++) {
        await delay(1000);
        const job = await api.documentJob(result.job_id, token);
        if (job.status === "completed")
          return api
            .documents(token)
            .then(
              (data) =>
                data.items.find((item) => item.id === result.document.id) ||
                result.document,
            );
        if (job.status === "failed")
          throw new Error(job.error_message || "Document processing failed");
      }
      throw new Error("Document processing is taking longer than expected");
    },
    onSuccess: (document) => {
      setDocumentId(document.id);
      setText("");
      setActive(null);
      setRecentResults([]);
      setDocumentAnswer("");
      setNotice(
        `${document.title} is ready · ${(document.classification || "general").replaceAll("_", " ")}.`,
      );
      queryClient.invalidateQueries({ queryKey: ["documents", "study"] });
    },
    onError: (error) => setNotice(error.message),
  });
  const createFolder = useMutation({
    mutationFn: () =>
      api.createDocumentFolder(folderName.trim(), folderId || null, token),
    onSuccess: (folder) => {
      setFolderName("");
      setNotice(`${folder.name} folder created.`);
      queryClient.invalidateQueries({ queryKey: ["document-folders"] });
    },
    onError: (error) => setNotice(error.message),
  });
  const deleteDocument = useMutation({
    mutationFn: (id: string) => api.deleteDocument(id, token),
    onSuccess: (_, id) => {
      if (documentId === id) setDocumentId("");
      setNotice("Document and its uploaded file were deleted.");
      queryClient.invalidateQueries({ queryKey: ["documents", "study"] });
      setConfirmDialog(null);
    },
    onError: (error) => setNotice(error.message),
  });
  const deleteFolder = useMutation({
    mutationFn: (id: string) => api.deleteDocumentFolder(id, token),
    onSuccess: (_, id) => {
      if (folderId === id) setFolderId("");
      setDocumentId("");
      setNotice("Folder, subfolders, and their uploaded files were deleted.");
      queryClient.invalidateQueries({ queryKey: ["document-folders"] });
      queryClient.invalidateQueries({ queryKey: ["documents", "study"] });
      setConfirmDialog(null);
    },
    onError: (error) => setNotice(error.message),
  });
  const moveDocument = useMutation({
    mutationFn: ({
      documentId,
      destination,
    }: {
      documentId: string;
      destination: string | null;
    }) => api.moveDocument(documentId, destination, token),
    onSuccess: (moved) => {
      queryClient.setQueryData<{ items: DocumentItem[]; total: number }>(
        ["documents", "study"],
        (current) =>
          current
            ? {
                ...current,
                items: current.items.map((item) =>
                  item.id === moved.id ? moved : item,
                ),
              }
            : current,
      );
      const destination =
        (folders.data || []).find((folder) => folder.id === moved.folder_id)
          ?.name || "My Library";
      setNotice(`${moved.title} moved to ${destination}.`);
      setDraggedDocumentId("");
      setDropTarget(null);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error) => {
      setNotice(`Could not move the document: ${error.message}`);
      setDraggedDocumentId("");
      setDropTarget(null);
    },
  });
  const speak = useMutation({
    mutationFn: async (content: string) => {
      const queued = await api.synthesize(
        content,
        active?.language || language,
        token,
        voiceId || undefined,
      );
      for (let i = 0; i < 120; i++) {
        await delay(1000);
        const job = await api.speechJob(queued.job_id, token);
        if (job.status === "failed")
          throw new Error(job.error_message || "Speech generation failed");
        if (job.status === "completed" && job.result.attachment_id)
          return {
            url: URL.createObjectURL(
              await api.speechAudio(job.result.attachment_id, token),
            ),
            engine: String(job.result.engine || ""),
          };
      }
      throw new Error(
        "Speech generation is taking longer than expected. Please try again.",
      );
    },
    onMutate: () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
        setAudioUrl(null);
      }
      setNotice("");
    },
    onSuccess: (result) => {
      setAudioUrl(result.url);
      if (voiceId && result.engine !== "xtts_v2")
        setNotice(
          "Your lecturer voice engine is not enabled yet, so EVA used the default reading voice.",
        );
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteStudyArtifact(id, token),
    onSuccess: (_, id) => {
      if (active?.id === id) setActive(null);
      queryClient.invalidateQueries({ queryKey: ["study-artifacts"] });
      setConfirmDialog(null);
    },
  });
  useEffect(
    () => () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    },
    [audioUrl],
  );
  const readable = useMemo(
    () => (active ? artifactText(active) : ""),
    [active],
  );
  const currentFolder =
    (folders.data || []).find((folder) => folder.id === folderId) || null;
  const visibleFolders = (folders.data || []).filter(
    (folder) => folder.parent_id === (folderId || null),
  );
  const visibleDocuments = (documents.data?.items || []).filter(
    (document) => (document.folder_id || null) === (folderId || null),
  );
  function submit(event: FormEvent) {
    event.preventDefault();
    if ((text.trim() || documentId) && selectedTypes.length) generate.mutate();
  }
  function toggleType(value: string) {
    setSelectedTypes((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    );
  }
  function requestFolderDelete(id: string, name: string) {
    setConfirmDialog({
      title: "Delete this folder?",
      subject: name,
      description:
        "This permanently removes the folder, every subfolder, and all uploaded documents stored inside it. This action cannot be undone.",
      confirmLabel: "Delete folder",
      onConfirm: () => deleteFolder.mutate(id),
    });
  }
  function requestDocumentDelete(id: string, name: string) {
    setConfirmDialog({
      title: "Delete this document?",
      subject: name,
      description:
        "The uploaded file, extracted content, and document search data will be permanently removed.",
      confirmLabel: "Delete document",
      onConfirm: () => deleteDocument.mutate(id),
    });
  }
  function requestArtifactDelete(id: string, name: string) {
    setConfirmDialog({
      title: "Delete this study material?",
      subject: name,
      description:
        "This generated learning material will be permanently removed from your Study Library.",
      confirmLabel: "Delete study item",
      onConfirm: () => remove.mutate(id),
    });
  }
  function startDocumentDrag(event: DragEvent<HTMLDivElement>, id: string) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/eva-document-id", id);
    setDraggedDocumentId(id);
    setNotice(
      "Drop the document onto a folder, or onto My Library to remove it from a folder.",
    );
  }
  function dropDocument(event: DragEvent, destination: string | null) {
    event.preventDefault();
    const id =
      event.dataTransfer.getData("text/eva-document-id") || draggedDocumentId;
    if (id) moveDocument.mutate({ documentId: id, destination });
  }
  return (
    <section className="study-page">
      <header className="study-head">
        <div>
          <span className="kicker">EVA STUDY STUDIO</span>
          <h1>
            Turn your modules
            <br />
            into <em>understanding.</em>
          </h1>
          <p>
            Upload private notes, learn in English or Kinyarwanda, and keep
            every result in your own library.
          </p>
        </div>
        <div className="study-seal">
          <BookOpen />
          <span>
            Your private
            <br />
            study library
          </span>
        </div>
      </header>
      <StudyRibbon />
      <div className="study-workbench">
        <form className="study-controls" onSubmit={submit}>
          <label>
            Upload notes or a module
            <small className="upload-location">
              Destination: {currentFolder?.name || "My Study Library"}
            </small>
            <Button
              type="button"
              variant="outline"
              onClick={() => fileInput.current?.click()}
              disabled={upload.isPending}
            >
              {upload.isPending ? (
                <LoaderCircle className="spin" />
              ) : (
                <FileUp />
              )}{" "}
              {upload.isPending
                ? "Processing…"
                : "Choose PDF, Word, text, or image"}
            </Button>
            <input
              ref={fileInput}
              className="hidden-file-input"
              type="file"
              accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.tif,.tiff"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload.mutate(file);
                event.target.value = "";
              }}
            />
          </label>
          <div className="or-rule">
            <span>OR PASTE NOTES</span>
          </div>
          <label>
            Source text
            <textarea
              rows={6}
              value={text}
              onChange={(event) => {
                setText(event.target.value);
                if (event.target.value) setDocumentId("");
              }}
              placeholder="Paste notes, a topic, or a word…"
            />
          </label>
          <label>
            What should EVA create?
            <span className="creation-hint">
              Choose one or several. EVA will create each selected item and save
              it to your library.
            </span>
            <div className="creation-picker">
              {types.map(({ value, label, description }) => (
                <button
                  type="button"
                  key={value}
                  className={selectedTypes.includes(value) ? "selected" : ""}
                  aria-pressed={selectedTypes.includes(value)}
                  onClick={() => toggleType(value)}
                >
                  <i>{selectedTypes.includes(value) ? "✓" : "+"}</i>
                  <span>
                    <strong>{label}</strong>
                    <small>{description}</small>
                  </span>
                </button>
              ))}
            </div>
            <span className="selection-count">
              {selectedTypes.length} selected
            </span>
          </label>
          <div className="control-row">
            <label>
              Output language
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="en">English</option>
                <option value="rw">Kinyarwanda</option>
              </select>
            </label>
            <label>
              Difficulty
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
              >
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </label>
            <label>
              Length
              <select
                value={length}
                onChange={(e) => setLength(e.target.value)}
              >
                <option value="short">Short</option>
                <option value="medium">Medium</option>
                <option value="long">Long</option>
              </select>
            </label>
          </div>
          {selectedTypes.some((type) =>
            [
              "quiz",
              "flashcards",
              "vocabulary",
              "true_false",
              "fill_blanks",
            ].includes(type),
          ) && (
            <label>
              Number of items
              <input
                type="number"
                min="1"
                max="20"
                value={count}
                onChange={(e) =>
                  setCount(Math.max(1, Math.min(20, Number(e.target.value))))
                }
              />
            </label>
          )}
          <Button
            disabled={
              generate.isPending ||
              (!text.trim() && !documentId) ||
              !selectedTypes.length
            }
          >
            {generate.isPending ? (
              <LoaderCircle className="spin" />
            ) : (
              <Sparkles />
            )}{" "}
            Create {selectedTypes.length || ""} study{" "}
            {selectedTypes.length === 1 ? "item" : "items"}
          </Button>
          {notice && <p className="study-notice">{notice}</p>}
          {generate.error && (
            <p className="form-error">{generate.error.message}</p>
          )}
        </form>
        <main className="study-result">
          {recentResults.length > 1 && (
            <nav
              className="batch-result-tabs"
              aria-label="Newly created study items"
            >
              {recentResults.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={active?.id === item.id ? "active" : ""}
                  onClick={() => setActive(item)}
                >
                  {item.artifact_type.replaceAll("_", " ")}
                </button>
              ))}
            </nav>
          )}
          {!active && documentId ? (
            <article className="study-document-reader">
              <header>
                <div>
                  <span>DOCUMENT PREVIEW</span>
                  <h2>{documentPreview.data?.title || "Opening document…"}</h2>
                  <p>
                    Read the extracted content, then ask EVA a focused question.
                  </p>
                </div>
                <Eye />
              </header>
              {documentPreview.isLoading ? (
                <div className="reader-loading">
                  <LoaderCircle className="spin" /> Preparing document…
                </div>
              ) : documentPreview.error ? (
                <p className="form-error">{documentPreview.error.message}</p>
              ) : (
                <div className="document-reading-content">
                  {documentPreview.data?.text}
                </div>
              )}
              <form
                className="document-reader-question"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (documentQuestion.trim()) askDocument.mutate();
                }}
              >
                <label>
                  Ask about this document
                  <input
                    value={documentQuestion}
                    onChange={(event) =>
                      setDocumentQuestion(event.target.value)
                    }
                    placeholder="What would you like EVA to explain?"
                  />
                </label>
                <Button
                  disabled={!documentQuestion.trim() || askDocument.isPending}
                >
                  {askDocument.isPending ? (
                    <LoaderCircle className="spin" />
                  ) : (
                    <Send />
                  )}{" "}
                  Ask EVA
                </Button>
              </form>
              {askDocument.error && (
                <p className="form-error">{askDocument.error.message}</p>
              )}
              {documentAnswer && (
                <section className="document-reader-answer">
                  <span>EVA ANSWER</span>
                  <p>{documentAnswer}</p>
                </section>
              )}
            </article>
          ) : !active ? (
            <div className="study-empty">
              <span>01</span>
              <BookOpen />
              <h2>
                Your learning material
                <br />
                will appear here.
              </h2>
              <p>
                Summarize, explain, translate, build questions, discover
                vocabulary and synonyms, or create revision cards.
              </p>
            </div>
          ) : (
            <>
              <Artifact artifact={active} />
              <div className="study-tools">
                <label>
                  Reading voice
                  <select
                    value={voiceId}
                    onChange={(e) => setVoiceId(e.target.value)}
                  >
                    <option value="">EVA default voice</option>
                    {voices.data?.items
                      .filter((v) => v.status === "active")
                      .map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.name} (lecturer voice)
                        </option>
                      ))}
                  </select>
                </label>
                <Button
                  variant="outline"
                  onClick={() => speak.mutate(readable)}
                  disabled={speak.isPending}
                >
                  {speak.isPending ? (
                    <LoaderCircle className="spin" />
                  ) : (
                    <Play />
                  )}{" "}
                  Read aloud
                </Button>
                <ExportMenu artifact={active} />
                {audioUrl && <audio controls autoPlay src={audioUrl} />}
              </div>
              {speak.error && (
                <p className="form-error">{speak.error.message}</p>
              )}
            </>
          )}
        </main>
        <aside className="study-library">
          <div className="library-title">
            <Library />
            <div>
              <strong>My Study Library</strong>
              <small>
                {folders.data?.length || 0} folders ·{" "}
                {documents.data?.total || 0} documents
              </small>
            </div>
          </div>
          <div className="library-pathbar">
            {folderId && (
              <button
                type="button"
                aria-label="Go back"
                onClick={() => setFolderId(currentFolder?.parent_id || "")}
              >
                <ChevronLeft />
              </button>
            )}
            <button
              type="button"
              className={dropTarget === "root" ? "drop-active" : ""}
              onClick={() => setFolderId("")}
              onDragOver={(event) => {
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                setDropTarget("root");
              }}
              onDragLeave={() => setDropTarget(null)}
              onDrop={(event) => dropDocument(event, null)}
            >
              My Library
            </button>
            {currentFolder && (
              <>
                <span>/</span>
                <strong>{currentFolder.name}</strong>
              </>
            )}
          </div>
          <div className="library-folder-create">
            <input
              value={folderName}
              onChange={(event) => setFolderName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && folderName.trim()) {
                  event.preventDefault();
                  createFolder.mutate();
                }
              }}
              placeholder={
                currentFolder
                  ? `New folder inside ${currentFolder.name}`
                  : "New folder name"
              }
              maxLength={120}
            />
            <button
              type="button"
              disabled={!folderName.trim() || createFolder.isPending}
              onClick={() => createFolder.mutate()}
              aria-label="Create folder"
            >
              {createFolder.isPending ? (
                <LoaderCircle className="spin" />
              ) : (
                <FolderPlus />
              )}
            </button>
          </div>
          <div className="folder-grid">
            {visibleFolders.map((folder) => (
              <div
                className={`folder-tile ${dropTarget === folder.id ? "drop-active" : ""}`}
                key={folder.id}
                onDragOver={(event) => {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "move";
                  setDropTarget(folder.id);
                }}
                onDragLeave={() => setDropTarget(null)}
                onDrop={(event) => dropDocument(event, folder.id)}
              >
                <button type="button" onClick={() => setFolderId(folder.id)}>
                  <span className="folder-icon">
                    <Folder fill="currentColor" />
                    <i>✓</i>
                  </span>
                  <strong title={folder.name}>{folder.name}</strong>
                </button>
                <button
                  className="folder-delete"
                  type="button"
                  aria-label={`Delete ${folder.name}`}
                  onClick={() => requestFolderDelete(folder.id, folder.name)}
                >
                  <Trash2 />
                </button>
              </div>
            ))}
          </div>
          {visibleDocuments.length > 0 && (
            <div className="library-documents">
              <span>DOCUMENTS</span>
              {visibleDocuments.map((document) => (
                <div
                  className={`library-document-row ${draggedDocumentId === document.id ? "dragging" : ""}`}
                  key={document.id}
                  draggable={!moveDocument.isPending}
                  onDragStart={(event) => startDocumentDrag(event, document.id)}
                  onDragEnd={() => {
                    setDraggedDocumentId("");
                    setDropTarget(null);
                  }}
                >
                  <button
                    type="button"
                    onClick={() => {
                      if (document.status === "ready") {
                        setDocumentId(document.id);
                        setText("");
                        setActive(null);
                        setRecentResults([]);
                        setDocumentAnswer("");
                      }
                    }}
                  >
                    <Eye />
                    <span>
                      <strong>{document.title}</strong>
                      <small>
                        {(document.classification || "general").replaceAll(
                          "_",
                          " ",
                        )}{" "}
                        · {document.status}
                      </small>
                    </span>
                  </button>
                  <button
                    type="button"
                    className="document-delete"
                    aria-label={`Delete ${document.title}`}
                    onClick={() =>
                      requestDocumentDelete(document.id, document.title)
                    }
                  >
                    <Trash2 />
                  </button>
                </div>
              ))}
            </div>
          )}
          {draggedDocumentId && (
            <div className="folder-drop-shelf">
              <span>MOVE TO</span>
              <button
                type="button"
                className={dropTarget === "root" ? "drop-active" : ""}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDropTarget("root");
                }}
                onDrop={(event) => dropDocument(event, null)}
              >
                My Library (no folder)
              </button>
              {(folders.data || [])
                .filter(
                  (folder) =>
                    folder.id !==
                    documents.data?.items.find(
                      (item) => item.id === draggedDocumentId,
                    )?.folder_id,
                )
                .map((folder) => (
                  <button
                    type="button"
                    key={folder.id}
                    className={dropTarget === folder.id ? "drop-active" : ""}
                    onDragOver={(event) => {
                      event.preventDefault();
                      setDropTarget(folder.id);
                    }}
                    onDrop={(event) => dropDocument(event, folder.id)}
                  >
                    <Folder />
                    {folder.name}
                  </button>
                ))}
            </div>
          )}
          {!folders.isLoading &&
            !visibleFolders.length &&
            !visibleDocuments.length && (
              <p className="library-empty-folder">
                This folder is empty. Create a subfolder or upload a document
                here.
              </p>
            )}
          <div className="saved-study-title">
            <span>GENERATED STUDY MATERIAL</span>
            <small>{library.data?.total || 0} items</small>
          </div>
          {library.isLoading && <p>Loading…</p>}
          {library.data?.items.map((item) => (
            <button
              className={`library-item ${active?.id === item.id ? "active" : ""}`}
              key={item.id}
              onClick={() => {
                setActive(item);
                setRecentResults([]);
              }}
            >
              <span>
                <strong>{item.title}</strong>
                <small>
                  {item.artifact_type.replaceAll("_", " ")} ·{" "}
                  {new Date(item.created_at).toLocaleDateString()}
                </small>
              </span>
              <Trash2
                onClick={(event) => {
                  event.stopPropagation();
                  requestArtifactDelete(item.id, item.title);
                }}
              />
            </button>
          ))}
        </aside>
      </div>
      <ConfirmDialog
        dialog={confirmDialog}
        busy={
          deleteDocument.isPending || deleteFolder.isPending || remove.isPending
        }
        onClose={() => setConfirmDialog(null)}
      />
    </section>
  );
}

function Artifact({ artifact }: { artifact: StudyArtifact }) {
  const c = artifact.content;
  return (
    <article className="artifact">
      <header>
        <span>{artifact.artifact_type.replaceAll("_", " ")}</span>
        <h2>{artifact.title}</h2>
        <p>
          {artifact.difficulty} ·{" "}
          {artifact.language === "rw" ? "Kinyarwanda" : "English"}
        </p>
      </header>
      {c.summary && <p className="artifact-lead">{c.summary}</p>}
      {c.explanation && <p className="artifact-lead">{c.explanation}</p>}
      {c.translated_text && (
        <p className="artifact-lead">{c.translated_text}</p>
      )}
      {!!c.key_points.length && (
        <ul>
          {c.key_points.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      )}
      {!!c.notes.length && (
        <ul>
          {c.notes.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      )}
      {!!c.synonyms.length && (
        <div className="word-chips">
          {c.synonyms.map((x) => (
            <span key={x}>{x}</span>
          ))}
        </div>
      )}
      {c.quiz.map((x, i) => (
        <section className="quiz-item" key={i}>
          <span>QUESTION {i + 1}</span>
          <h3>{x.question}</h3>
          {x.options.map((option) => (
            <p key={option}>○ {option}</p>
          ))}
          <details>
            <summary>Show answer</summary>
            <strong>{x.answer}</strong>
            <p>{x.explanation}</p>
          </details>
          <Cites ids={x.source_ids} />
        </section>
      ))}
      <div className="flash-grid">
        {c.flashcards.map((x, i) => (
          <section key={i}>
            <span>FRONT</span>
            <h3>{x.front}</h3>
            <hr />
            <span>BACK</span>
            <p>{x.back}</p>
            <Cites ids={x.source_ids} />
          </section>
        ))}
      </div>
      {c.vocabulary.map((x, i) => (
        <section className="vocab" key={i}>
          <h3>{x.term}</h3>
          <p>{x.definition}</p>
          {x.synonyms.length > 0 && (
            <small>Synonyms: {x.synonyms.join(", ")}</small>
          )}
          {x.translation && <p>Translation: {x.translation}</p>}
          <Cites ids={x.source_ids} />
        </section>
      ))}
      {artifact.source_refs.length > 0 && (
        <details className="sources">
          <summary>View {artifact.source_refs.length} source passages</summary>
          {artifact.source_refs.map((ref) => (
            <p key={ref.id}>
              <strong>[{ref.id}]</strong> {ref.excerpt}{" "}
              {ref.page_number && <small>p. {ref.page_number}</small>}
            </p>
          ))}
        </details>
      )}
    </article>
  );
}
function Cites({ ids }: { ids: string[] }) {
  return ids.length ? (
    <div className="cites">
      {ids.map((id) => (
        <span key={id}>[{id}]</span>
      ))}
    </div>
  ) : null;
}
function artifactText(a: StudyArtifact) {
  const c = a.content;
  return [
    c.summary,
    c.explanation,
    c.translated_text,
    ...c.key_points,
    ...c.notes,
    ...c.synonyms,
    ...c.quiz.flatMap((x) => [x.question, x.answer, x.explanation]),
    ...c.flashcards.flatMap((x) => [x.front, x.back]),
    ...c.vocabulary.flatMap((x) => [
      x.term,
      x.definition,
      x.synonyms.join(", "),
    ]),
  ]
    .filter(Boolean)
    .join("\n\n")
    .slice(0, 20000);
}
function safeName(value: string) {
  return (
    value
      .replace(/[^a-z0-9]+/gi, "-")
      .replace(/^-|-$/g, "")
      .toLowerCase() || "eva-study"
  );
}
type FolderChoice = { id: string; label: string };
function folderOptions(folders: DocumentFolder[]): FolderChoice[] {
  const children = new Map<string | null, DocumentFolder[]>();
  folders.forEach((folder) =>
    children.set(folder.parent_id, [
      ...(children.get(folder.parent_id) || []),
      folder,
    ]),
  );
  const choices: FolderChoice[] = [];
  const visit = (parentId: string | null, depth: number) => {
    for (const folder of children.get(parentId) || []) {
      choices.push({
        id: folder.id,
        label: `${"— ".repeat(depth)}${folder.name}`,
      });
      visit(folder.id, depth + 1);
    }
  };
  visit(null, 0);
  return choices;
}
function folderDocumentLabel(document: DocumentItem, folders: FolderChoice[]) {
  const folder = folders.find((item) => item.id === document.folder_id);
  const classification = (document.classification || "general").replaceAll(
    "_",
    " ",
  );
  return `${folder ? `${folder.label} / ` : ""}${document.title} · ${classification}`;
}
function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function tableRows(a: StudyArtifact): string[][] {
  const c = a.content;
  if (c.quiz.length)
    return [
      ["Question", "Options", "Answer", "Explanation"],
      ...c.quiz.map((x) => [
        x.question,
        x.options.join(" | "),
        x.answer,
        x.explanation,
      ]),
    ];
  if (c.flashcards.length)
    return [["Front", "Back"], ...c.flashcards.map((x) => [x.front, x.back])];
  if (c.vocabulary.length)
    return [
      ["Term", "Definition", "Synonyms", "Translation"],
      ...c.vocabulary.map((x) => [
        x.term,
        x.definition,
        x.synonyms.join(", "),
        x.translation || "",
      ]),
    ];
  return [];
}
function ExportMenu({ artifact }: { artifact: StudyArtifact }) {
  const name = safeName(artifact.title),
    rows = tableRows(artifact);
  async function pdf() {
    const { jsPDF } = await import("jspdf");
    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text(artifact.title, 15, 18);
    doc.setFontSize(10);
    const lines = doc.splitTextToSize(artifactText(artifact), 180);
    let y = 28;
    for (const line of lines) {
      if (y > 282) {
        doc.addPage();
        y = 15;
      }
      doc.text(line, 15, y);
      y += 5;
    }
    doc.save(`${name}.pdf`);
  }
  async function word() {
    const { Document, Packer, Paragraph, HeadingLevel } = await import("docx");
    const paragraphs = [
      new Paragraph({ text: artifact.title, heading: HeadingLevel.TITLE }),
      ...artifactText(artifact)
        .split("\n")
        .map((text) => new Paragraph({ text })),
    ];
    download(
      await Packer.toBlob(
        new Document({ sections: [{ children: paragraphs }] }),
      ),
      `${name}.docx`,
    );
  }
  function excel() {
    const escape = (v: string) =>
      v
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    const html = `<html><meta charset="utf-8"><table>${rows.map((row) => `<tr>${row.map((cell) => `<td>${escape(cell)}</td>`).join("")}</tr>`).join("")}</table></html>`;
    download(
      new Blob([html], { type: "application/vnd.ms-excel" }),
      `${name}.xls`,
    );
  }
  return (
    <div className="export-actions">
      <Button variant="outline" onClick={pdf}>
        <Download /> PDF
      </Button>
      <Button variant="outline" onClick={word}>
        <Download /> Word
      </Button>
      {rows.length > 0 && (
        <Button variant="outline" onClick={excel}>
          <Download /> Excel
        </Button>
      )}
    </div>
  );
}
