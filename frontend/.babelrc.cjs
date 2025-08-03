module.exports = {
  presets: [
    '@babel/preset-env',
    '@babel/preset-typescript',
    '@babel/preset-react'
  ],
  plugins: [
    function() {
      return {
        visitor: {
          MetaProperty(path) {
            path.replaceWithSourceString('process');
          }
        }
      }
    }
  ]
};