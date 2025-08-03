module.exports = {
  process(sourceText, sourcePath) {
    // Replace import.meta.env with process.env
    return {
      code: sourceText
        .replace(/import\.meta\.env\.VITE_API_URL/g, 'process.env.VITE_API_URL')
        .replace(/import\.meta\.env\.VITE_WS_URL/g, 'process.env.VITE_WS_URL')
        .replace(/import\.meta\.env\.VITE_PUBLIC_VAPID_KEY/g, 'process.env.VITE_PUBLIC_VAPID_KEY')
        .replace(/import\.meta\.env\.MODE/g, 'process.env.NODE_ENV')
        .replace(/import\.meta\.env/g, 'process.env'),
    };
  },
};