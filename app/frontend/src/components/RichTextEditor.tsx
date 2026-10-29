import { useEffect } from 'react'
import { useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { Placeholder } from '@tiptap/extensions'
import { Link, RichTextEditor as MantineRichTextEditor } from '@mantine/tiptap'
import { Markdown, type MarkdownStorage } from 'tiptap-markdown'

declare module '@tiptap/core' {
  interface Storage {
    markdown: MarkdownStorage
  }
}

interface RichTextEditorProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  minHeight?: number
}

export function RichTextEditor({
  value,
  onChange,
  placeholder,
  minHeight = 200,
}: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      // StarterKit 3 brings Underline and a Link of its own; Mantine's Link
      // is the one its toolbar controls expect.
      StarterKit.configure({
        heading: { levels: [2, 3, 4] },
        link: false,
      }),
      Link,
      Placeholder.configure({
        placeholder: placeholder ?? '',
      }),
      Markdown.configure({
        html: false,
        breaks: true,
        transformPastedText: true,
        transformCopiedText: true,
      }),
    ],
    content: value,
    // Tiptap 3 no longer re-renders on every change; the toolbar's active
    // states (bold, heading, ...) need it.
    shouldRerenderOnTransaction: true,
    onUpdate: ({ editor }) => {
      onChange(editor.storage.markdown.getMarkdown())
    },
  })

  useEffect(() => {
    // In StrictMode React mounts twice and Tiptap destroys the first editor,
    // which empties its storage.
    if (!editor || editor.isDestroyed) return
    const current = editor.storage.markdown.getMarkdown()
    if (value !== current) {
      editor.commands.setContent(value || '')
    }
  }, [value, editor])

  if (!editor) return null

  return (
    <MantineRichTextEditor editor={editor}>
      <MantineRichTextEditor.Toolbar sticky>
        <MantineRichTextEditor.ControlsGroup>
          <MantineRichTextEditor.Bold />
          <MantineRichTextEditor.Italic />
          <MantineRichTextEditor.Underline />
          <MantineRichTextEditor.Strikethrough />
          <MantineRichTextEditor.ClearFormatting />
        </MantineRichTextEditor.ControlsGroup>

        <MantineRichTextEditor.ControlsGroup>
          <MantineRichTextEditor.H2 />
          <MantineRichTextEditor.H3 />
          <MantineRichTextEditor.H4 />
        </MantineRichTextEditor.ControlsGroup>

        <MantineRichTextEditor.ControlsGroup>
          <MantineRichTextEditor.BulletList />
          <MantineRichTextEditor.OrderedList />
          <MantineRichTextEditor.Blockquote />
          <MantineRichTextEditor.Hr />
        </MantineRichTextEditor.ControlsGroup>

        <MantineRichTextEditor.ControlsGroup>
          <MantineRichTextEditor.Link />
          <MantineRichTextEditor.Unlink />
        </MantineRichTextEditor.ControlsGroup>

        <MantineRichTextEditor.ControlsGroup>
          <MantineRichTextEditor.Undo />
          <MantineRichTextEditor.Redo />
        </MantineRichTextEditor.ControlsGroup>
      </MantineRichTextEditor.Toolbar>

      <MantineRichTextEditor.Content style={{ minHeight }} />
    </MantineRichTextEditor>
  )
}
