/**
 * @format
 */

import { AppRegistry } from 'react-native';
import App from './src/App';
import { name as appName } from './app.json';
import 'react-native-gesture-handler';

// Enable React Query devtools in development
if (__DEV__) {
  import('./src/utils/reactQueryDevtools');
}

AppRegistry.registerComponent(appName, () => App);