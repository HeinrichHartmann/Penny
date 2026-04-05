import { reactive } from 'vue/dist/vue.esm-bundler.js';

export const createImportViewState = ({ uploadSelectedFiles }) => {
  const dragState = reactive({
    isDragging: false,
  });

  const handleDragOver = (event) => {
    event.preventDefault();
    dragState.isDragging = true;
  };

  const handleDragLeave = () => {
    dragState.isDragging = false;
  };

  const handleDrop = async (event) => {
    event.preventDefault();
    dragState.isDragging = false;

    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
      await uploadSelectedFiles(files);
    }
  };

  const handleFileSelect = async (event) => {
    const files = Array.from(event.target.files);
    if (files.length > 0) {
      await uploadSelectedFiles(files);
    }
    event.target.value = '';
  };

  return {
    dragState,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleFileSelect,
  };
};
