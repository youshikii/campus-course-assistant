<template><div class="markdown-content" v-html="html" /></template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({ content: { type: String, default: '' } })
const html = computed(() =>
  DOMPurify.sanitize(marked.parse(props.content, { breaks: true, gfm: true }), {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['img', 'form', 'input', 'style']
  })
)
</script>

<style>
.markdown-content {
  line-height: 1.85;
  overflow-wrap: anywhere;
}
.markdown-content p,
.markdown-content ul,
.markdown-content ol,
.markdown-content pre,
.markdown-content blockquote,
.markdown-content table {
  margin: 0 0 12px;
}
.markdown-content ul {
  list-style: disc;
  padding-left: 24px;
}
.markdown-content ol {
  list-style: decimal;
  padding-left: 24px;
}
.markdown-content h1,
.markdown-content h2,
.markdown-content h3 {
  margin: 18px 0 10px;
}
.markdown-content pre {
  background: #f3f5f8;
  padding: 14px;
  border-radius: 8px;
  overflow-x: auto;
}
.markdown-content code {
  font-size: 13px;
  background: #f3f5f8;
  border-radius: 4px;
  padding: 2px 4px;
}
.markdown-content pre code {
  padding: 0;
}
.markdown-content a {
  color: #3665d5;
  text-decoration: underline;
}
.markdown-content blockquote {
  border-left: 3px solid #9aaff0;
  padding-left: 14px;
  color: #667085;
}
.markdown-content table {
  border-collapse: collapse;
  display: block;
  overflow: auto;
}
.markdown-content th,
.markdown-content td {
  border: 1px solid #e4e7ed;
  padding: 8px 12px;
}
.markdown-content > :last-child {
  margin-bottom: 0;
}
</style>
