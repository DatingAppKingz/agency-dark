# OAuth Token Storage Guidelines

## Overview
This document provides comprehensive guidelines for securely storing OAuth tokens across different platforms and environments. Proper token storage is critical for maintaining security while ensuring a smooth user experience.

## Table of Contents
- [Token Types and Sensitivity](#token-types-and-sensitivity)
- [Storage Options by Platform](#storage-options-by-platform)
- [Web Applications](#web-applications)
- [Mobile Applications](#mobile-applications)
- [Desktop Applications](#desktop-applications)
- [Backend Services](#backend-services)
- [Encryption Strategies](#encryption-strategies)
- [Token Lifecycle Management](#token-lifecycle-management)
- [Security Best Practices](#security-best-practices)
- [Compliance Considerations](#compliance-considerations)

---

## Token Types and Sensitivity

### Token Classification

| Token Type | Sensitivity | Lifetime | Storage Requirements |
|------------|------------|----------|---------------------|
| **Access Token** | High | Short (1 hour) | Memory or secure temporary storage |
| **Refresh Token** | Critical | Long (30 days) | Encrypted persistent storage |
| **ID Token** | Medium | Short (1 hour) | Memory or secure temporary storage |
| **Authorization Code** | High | Very Short (10 min) | Memory only |
| **Client Secret** | Critical | Permanent | Secure vault/HSM |

### Risk Assessment

```python
# backend/security/token_risk_assessment.py
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict

class TokenRiskLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class TokenRiskProfile:
    token_type: str
    risk_level: TokenRiskLevel
    threats: List[str]
    mitigations: List[str]

class TokenRiskAssessment:
    """
    Assess and manage token storage risks
    """
    
    RISK_PROFILES = {
        "access_token": TokenRiskProfile(
            token_type="access_token",
            risk_level=TokenRiskLevel.HIGH,
            threats=[
                "XSS attacks can steal from JavaScript",
                "Network interception if not using HTTPS",
                "Browser extensions can access",
                "Replay attacks if token leaked"
            ],
            mitigations=[
                "Store in memory only when possible",
                "Use httpOnly cookies for server-side apps",
                "Implement short expiration times",
                "Use token binding when available"
            ]
        ),
        "refresh_token": TokenRiskProfile(
            token_type="refresh_token",
            risk_level=TokenRiskLevel.CRITICAL,
            threats=[
                "Persistent XSS can exfiltrate",
                "Device compromise exposes token",
                "Long lifetime increases exposure window",
                "Can be used to generate new access tokens"
            ],
            mitigations=[
                "Never store in browser localStorage",
                "Encrypt at rest",
                "Implement refresh token rotation",
                "Use secure device storage (Keychain/Keystore)"
            ]
        ),
        "client_secret": TokenRiskProfile(
            token_type="client_secret",
            risk_level=TokenRiskLevel.CRITICAL,
            threats=[
                "Code repository exposure",
                "Client-side storage impossible",
                "Reverse engineering of apps",
                "Memory dumps can expose"
            ],
            mitigations=[
                "Never store in client-side code",
                "Use environment variables",
                "Implement secret rotation",
                "Use HSM or secret management service"
            ]
        )
    }
    
    @classmethod
    def assess_storage_method(
        cls,
        token_type: str,
        storage_method: str,
        platform: str
    ) -> Dict:
        """
        Assess if storage method is appropriate for token type
        """
        profile = cls.RISK_PROFILES.get(token_type)
        if not profile:
            return {"error": "Unknown token type"}
        
        # Define acceptable storage methods by platform and token type
        acceptable_storage = {
            ("access_token", "web"): ["memory", "session_storage", "httponly_cookie"],
            ("access_token", "mobile"): ["memory", "secure_storage"],
            ("refresh_token", "web"): ["httponly_cookie", "none"],
            ("refresh_token", "mobile"): ["keychain", "keystore"],
            ("client_secret", "backend"): ["env_var", "secret_manager", "hsm"]
        }
        
        key = (token_type, platform)
        acceptable = acceptable_storage.get(key, [])
        
        is_acceptable = storage_method in acceptable
        
        return {
            "token_type": token_type,
            "platform": platform,
            "storage_method": storage_method,
            "risk_level": profile.risk_level.name,
            "is_acceptable": is_acceptable,
            "recommendation": acceptable[0] if acceptable else "not_recommended",
            "threats": profile.threats if not is_acceptable else [],
            "mitigations": profile.mitigations
        }
```

---

## Storage Options by Platform

### Comparison Matrix

| Platform | Storage Method | Security Level | Persistence | Best For |
|----------|---------------|----------------|-------------|----------|
| **Web - Memory** | JavaScript Variable | High | None | Access tokens |
| **Web - SessionStorage** | Browser Session | Medium | Session | Temporary tokens |
| **Web - HttpOnly Cookie** | Server Cookie | High | Configurable | All tokens |
| **Mobile - Keychain/Keystore** | OS Secure Storage | Very High | Persistent | Refresh tokens |
| **Desktop - OS Credential Store** | System Vault | High | Persistent | All tokens |
| **Backend - Environment** | Env Variables | Medium | Process | Secrets |
| **Backend - Secret Manager** | Cloud Service | Very High | Persistent | All secrets |

---

## Web Applications

### Browser Storage Options

```typescript
// frontend/src/services/token-storage/web-storage.ts
import CryptoJS from 'crypto-js';

interface TokenStorage {
    store(token: string, type: TokenType): void;
    retrieve(type: TokenType): string | null;
    remove(type: TokenType): void;
    clear(): void;
}

enum TokenType {
    ACCESS = 'access_token',
    REFRESH = 'refresh_token',
    ID = 'id_token'
}

/**
 * Memory-only storage (most secure for SPA)
 */
class MemoryTokenStorage implements TokenStorage {
    private tokens: Map<TokenType, string> = new Map();
    
    store(token: string, type: TokenType): void {
        this.tokens.set(type, token);
    }
    
    retrieve(type: TokenType): string | null {
        return this.tokens.get(type) || null;
    }
    
    remove(type: TokenType): void {
        this.tokens.delete(type);
    }
    
    clear(): void {
        this.tokens.clear();
    }
}

/**
 * SessionStorage with encryption (medium security)
 */
class EncryptedSessionStorage implements TokenStorage {
    private encryptionKey: string;
    
    constructor() {
        // Generate or retrieve encryption key
        this.encryptionKey = this.getOrGenerateKey();
    }
    
    private getOrGenerateKey(): string {
        let key = sessionStorage.getItem('storage_key');
        if (!key) {
            key = CryptoJS.lib.WordArray.random(256/8).toString();
            sessionStorage.setItem('storage_key', key);
        }
        return key;
    }
    
    store(token: string, type: TokenType): void {
        // Never store refresh tokens in sessionStorage
        if (type === TokenType.REFRESH) {
            console.warn('Refresh tokens should not be stored in sessionStorage');
            return;
        }
        
        const encrypted = CryptoJS.AES.encrypt(token, this.encryptionKey).toString();
        sessionStorage.setItem(type, encrypted);
    }
    
    retrieve(type: TokenType): string | null {
        const encrypted = sessionStorage.getItem(type);
        if (!encrypted) return null;
        
        try {
            const decrypted = CryptoJS.AES.decrypt(encrypted, this.encryptionKey);
            return decrypted.toString(CryptoJS.enc.Utf8);
        } catch {
            return null;
        }
    }
    
    remove(type: TokenType): void {
        sessionStorage.removeItem(type);
    }
    
    clear(): void {
        Object.values(TokenType).forEach(type => {
            sessionStorage.removeItem(type);
        });
    }
}

/**
 * HttpOnly Cookie storage (handled server-side)
 */
class CookieTokenStorage implements TokenStorage {
    store(token: string, type: TokenType): void {
        // Send to backend to set HttpOnly cookie
        fetch('/api/auth/store-token', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, type })
        });
    }
    
    retrieve(type: TokenType): string | null {
        // Tokens in HttpOnly cookies are not accessible via JS
        // They are automatically sent with requests
        return null;
    }
    
    remove(type: TokenType): void {
        fetch('/api/auth/remove-token', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type })
        });
    }
    
    clear(): void {
        fetch('/api/auth/clear-tokens', {
            method: 'POST',
            credentials: 'include'
        });
    }
}

/**
 * Service Worker storage (for PWA)
 */
class ServiceWorkerStorage implements TokenStorage {
    private worker: ServiceWorker | null = null;
    
    constructor() {
        this.initServiceWorker();
    }
    
    private async initServiceWorker() {
        if ('serviceWorker' in navigator) {
            const registration = await navigator.serviceWorker.register('/sw.js');
            this.worker = registration.active || registration.installing;
        }
    }
    
    store(token: string, type: TokenType): void {
        if (!this.worker) return;
        
        this.worker.postMessage({
            action: 'store_token',
            type,
            token
        });
    }
    
    async retrieve(type: TokenType): Promise<string | null> {
        if (!this.worker) return null;
        
        return new Promise((resolve) => {
            const channel = new MessageChannel();
            
            channel.port1.onmessage = (event) => {
                resolve(event.data.token);
            };
            
            this.worker!.postMessage({
                action: 'get_token',
                type
            }, [channel.port2]);
        });
    }
    
    remove(type: TokenType): void {
        if (!this.worker) return;
        
        this.worker.postMessage({
            action: 'remove_token',
            type
        });
    }
    
    clear(): void {
        if (!this.worker) return;
        
        this.worker.postMessage({
            action: 'clear_tokens'
        });
    }
}

/**
 * Storage factory based on security requirements
 */
class TokenStorageFactory {
    static create(securityLevel: 'high' | 'medium' | 'low'): TokenStorage {
        switch (securityLevel) {
            case 'high':
                // Use memory storage for highest security
                return new MemoryTokenStorage();
            case 'medium':
                // Use encrypted session storage
                return new EncryptedSessionStorage();
            case 'low':
                // Not recommended, but available
                console.warn('Low security storage not recommended for tokens');
                return new EncryptedSessionStorage();
            default:
                return new MemoryTokenStorage();
        }
    }
}
```

### Server-Side Cookie Implementation

```python
# backend/security/cookie_token_storage.py
from fastapi import Response, Request, HTTPException
from typing import Optional, Dict
import jwt
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

class SecureCookieTokenStorage:
    """
    Secure HttpOnly cookie implementation for token storage
    """
    
    def __init__(self, encryption_key: bytes):
        self.cipher = Fernet(encryption_key)
    
    def set_token_cookie(
        self,
        response: Response,
        token: str,
        token_type: str,
        max_age: Optional[int] = None
    ) -> None:
        """
        Set secure HttpOnly cookie with token
        """
        # Encrypt token
        encrypted = self.cipher.encrypt(token.encode()).decode()
        
        # Cookie name based on type
        cookie_name = f"__Host-{token_type}"  # __Host- prefix for security
        
        # Set cookie with security flags
        response.set_cookie(
            key=cookie_name,
            value=encrypted,
            max_age=max_age or 3600,  # Default 1 hour
            expires=datetime.utcnow() + timedelta(seconds=max_age or 3600),
            path="/",
            domain=None,  # Current domain only
            secure=True,  # HTTPS only
            httponly=True,  # Not accessible via JavaScript
            samesite="strict"  # CSRF protection
        )
        
        # Set fingerprint cookie (for additional security)
        fingerprint = self.generate_fingerprint(token)
        response.set_cookie(
            key="__Host-Fingerprint",
            value=fingerprint,
            max_age=max_age or 3600,
            secure=True,
            httponly=True,
            samesite="strict"
        )
    
    def get_token_from_cookie(
        self,
        request: Request,
        token_type: str
    ) -> Optional[str]:
        """
        Retrieve and decrypt token from cookie
        """
        cookie_name = f"__Host-{token_type}"
        
        # Get encrypted token
        encrypted = request.cookies.get(cookie_name)
        if not encrypted:
            return None
        
        try:
            # Decrypt token
            token = self.cipher.decrypt(encrypted.encode()).decode()
            
            # Validate fingerprint
            fingerprint = request.cookies.get("__Host-Fingerprint")
            if not self.validate_fingerprint(token, fingerprint):
                raise ValueError("Invalid token fingerprint")
            
            return token
            
        except Exception as e:
            logger.warning(f"Failed to decrypt token cookie: {e}")
            return None
    
    def remove_token_cookie(
        self,
        response: Response,
        token_type: str
    ) -> None:
        """
        Remove token cookie
        """
        cookie_name = f"__Host-{token_type}"
        
        response.set_cookie(
            key=cookie_name,
            value="",
            max_age=0,
            expires=datetime.utcnow() - timedelta(days=1),
            path="/",
            secure=True,
            httponly=True,
            samesite="strict"
        )
    
    def generate_fingerprint(self, token: str) -> str:
        """
        Generate token fingerprint for additional validation
        """
        import hashlib
        
        # Use part of token for fingerprint
        token_prefix = token[:20] if len(token) > 20 else token
        return hashlib.sha256(f"fingerprint:{token_prefix}".encode()).hexdigest()
    
    def validate_fingerprint(self, token: str, fingerprint: str) -> bool:
        """
        Validate token fingerprint
        """
        expected = self.generate_fingerprint(token)
        return hmac.compare_digest(expected, fingerprint)
```

---

## Mobile Applications

### iOS Keychain Implementation

```swift
// iOS/TokenStorage/KeychainTokenStorage.swift
import Foundation
import Security

class KeychainTokenStorage {
    private let serviceName = "com.agencydark.oauth"
    
    enum TokenType: String {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case idToken = "id_token"
    }
    
    enum KeychainError: Error {
        case itemNotFound
        case duplicateItem
        case invalidData
        case unhandledError(status: OSStatus)
    }
    
    // MARK: - Store Token
    func store(token: String, type: TokenType) throws {
        guard let data = token.data(using: .utf8) else {
            throw KeychainError.invalidData
        }
        
        // Delete existing item if present
        try? delete(type: type)
        
        // Build query
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: type.rawValue,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            // Additional security attributes
            kSecAttrSynchronizable as String: false,  // Don't sync to iCloud
            kSecAttrIsInvisible as String: true,      // Hide from user
        ]
        
        // Add to keychain
        let status = SecItemAdd(query as CFDictionary, nil)
        
        guard status == errSecSuccess else {
            throw KeychainError.unhandledError(status: status)
        }
        
        // For refresh tokens, add additional protection
        if type == .refreshToken {
            try enableBiometricProtection(for: type)
        }
    }
    
    // MARK: - Retrieve Token
    func retrieve(type: TokenType) throws -> String {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: type.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        switch status {
        case errSecSuccess:
            guard let data = result as? Data,
                  let token = String(data: data, encoding: .utf8) else {
                throw KeychainError.invalidData
            }
            return token
            
        case errSecItemNotFound:
            throw KeychainError.itemNotFound
            
        default:
            throw KeychainError.unhandledError(status: status)
        }
    }
    
    // MARK: - Delete Token
    func delete(type: TokenType) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: type.rawValue
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.unhandledError(status: status)
        }
    }
    
    // MARK: - Biometric Protection
    private func enableBiometricProtection(for type: TokenType) throws {
        // Create access control with biometric authentication
        var error: Unmanaged<CFError>?
        
        guard let accessControl = SecAccessControlCreateWithFlags(
            kCFAllocatorDefault,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            [.biometryCurrentSet, .devicePasscode],
            &error
        ) else {
            if let error = error {
                throw error.takeRetainedValue() as Error
            }
            throw KeychainError.invalidData
        }
        
        // Update the item with biometric protection
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: type.rawValue
        ]
        
        let attributes: [String: Any] = [
            kSecAttrAccessControl as String: accessControl
        ]
        
        let status = SecItemUpdate(
            query as CFDictionary,
            attributes as CFDictionary
        )
        
        guard status == errSecSuccess else {
            throw KeychainError.unhandledError(status: status)
        }
    }
    
    // MARK: - Clear All Tokens
    func clearAll() throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.unhandledError(status: status)
        }
    }
}
```

### Android Keystore Implementation

```kotlin
// Android/TokenStorage/KeystoreTokenStorage.kt
package com.agencydark.oauth.storage

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import android.util.Base64

class KeystoreTokenStorage(private val context: Context) {
    
    companion object {
        private const val KEYSTORE_PROVIDER = "AndroidKeyStore"
        private const val KEY_ALIAS = "AgencyDarkTokenKey"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val SHARED_PREFS_NAME = "secure_tokens"
    }
    
    enum class TokenType(val key: String) {
        ACCESS_TOKEN("access_token"),
        REFRESH_TOKEN("refresh_token"),
        ID_TOKEN("id_token")
    }
    
    private val keyStore: KeyStore = KeyStore.getInstance(KEYSTORE_PROVIDER).apply {
        load(null)
    }
    
    private val encryptedPrefs: SharedPreferences by lazy {
        createEncryptedSharedPreferences()
    }
    
    // Create encrypted SharedPreferences
    private fun createEncryptedSharedPreferences(): SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .setRequestStrongBoxBacked(true) // Use hardware security module if available
            .build()
        
        return EncryptedSharedPreferences.create(
            context,
            SHARED_PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }
    
    // Store token with additional encryption
    fun storeToken(token: String, type: TokenType) {
        // For refresh tokens, add extra encryption layer
        val tokenToStore = if (type == TokenType.REFRESH_TOKEN) {
            encryptWithKeystore(token)
        } else {
            token
        }
        
        encryptedPrefs.edit()
            .putString(type.key, tokenToStore)
            .apply()
    }
    
    // Retrieve token
    fun retrieveToken(type: TokenType): String? {
        val storedValue = encryptedPrefs.getString(type.key, null)
        
        return if (type == TokenType.REFRESH_TOKEN && storedValue != null) {
            decryptWithKeystore(storedValue)
        } else {
            storedValue
        }
    }
    
    // Delete token
    fun deleteToken(type: TokenType) {
        encryptedPrefs.edit()
            .remove(type.key)
            .apply()
    }
    
    // Clear all tokens
    fun clearAll() {
        encryptedPrefs.edit()
            .clear()
            .apply()
    }
    
    // Additional Keystore encryption for sensitive tokens
    private fun encryptWithKeystore(plaintext: String): String {
        val key = getOrCreateSecretKey()
        
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key)
        
        val iv = cipher.iv
        val ciphertext = cipher.doFinal(plaintext.toByteArray())
        
        // Combine IV and ciphertext
        val combined = iv + ciphertext
        
        return Base64.encodeToString(combined, Base64.DEFAULT)
    }
    
    private fun decryptWithKeystore(encrypted: String): String {
        val key = getOrCreateSecretKey()
        
        val combined = Base64.decode(encrypted, Base64.DEFAULT)
        
        // Extract IV and ciphertext
        val iv = combined.sliceArray(0..11)
        val ciphertext = combined.sliceArray(12 until combined.size)
        
        val cipher = Cipher.getInstance(TRANSFORMATION)
        val spec = GCMParameterSpec(128, iv)
        cipher.init(Cipher.DECRYPT_MODE, key, spec)
        
        val plaintext = cipher.doFinal(ciphertext)
        
        return String(plaintext)
    }
    
    private fun getOrCreateSecretKey(): SecretKey {
        return if (keyStore.containsAlias(KEY_ALIAS)) {
            (keyStore.getEntry(KEY_ALIAS, null) as KeyStore.SecretKeyEntry).secretKey
        } else {
            generateSecretKey()
        }
    }
    
    private fun generateSecretKey(): SecretKey {
        val keyGenerator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            KEYSTORE_PROVIDER
        )
        
        val spec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setUserAuthenticationRequired(false) // Set to true for biometric
            .setRandomizedEncryptionRequired(true)
            .build()
        
        keyGenerator.init(spec)
        return keyGenerator.generateKey()
    }
    
    // Check if biometric authentication is available
    fun isBiometricAvailable(): Boolean {
        val biometricManager = androidx.biometric.BiometricManager.from(context)
        return biometricManager.canAuthenticate(
            androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
        ) == androidx.biometric.BiometricManager.BIOMETRIC_SUCCESS
    }
}
```

---

## Desktop Applications

### Electron Secure Storage

```typescript
// desktop/src/token-storage/electron-storage.ts
import { safeStorage, app } from 'electron';
import * as keytar from 'keytar';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

class ElectronTokenStorage {
    private serviceName = 'AgencyDark';
    private storageMethod: 'keytar' | 'safeStorage' | 'encrypted_file';
    
    constructor() {
        // Determine best storage method
        this.storageMethod = this.determineBestStorage();
    }
    
    private determineBestStorage(): 'keytar' | 'safeStorage' | 'encrypted_file' {
        // Prefer OS credential store via keytar
        if (this.isKeytarAvailable()) {
            return 'keytar';
        }
        
        // Fall back to Electron's safeStorage
        if (safeStorage.isEncryptionAvailable()) {
            return 'safeStorage';
        }
        
        // Last resort: encrypted file
        return 'encrypted_file';
    }
    
    private isKeytarAvailable(): boolean {
        try {
            // Test keytar availability
            require('keytar');
            return true;
        } catch {
            return false;
        }
    }
    
    async storeToken(token: string, type: string): Promise<void> {
        switch (this.storageMethod) {
            case 'keytar':
                await this.storeWithKeytar(token, type);
                break;
            case 'safeStorage':
                await this.storeWithSafeStorage(token, type);
                break;
            case 'encrypted_file':
                await this.storeInEncryptedFile(token, type);
                break;
        }
    }
    
    async retrieveToken(type: string): Promise<string | null> {
        switch (this.storageMethod) {
            case 'keytar':
                return await this.retrieveFromKeytar(type);
            case 'safeStorage':
                return await this.retrieveFromSafeStorage(type);
            case 'encrypted_file':
                return await this.retrieveFromEncryptedFile(type);
        }
    }
    
    // Keytar implementation (OS credential store)
    private async storeWithKeytar(token: string, type: string): Promise<void> {
        await keytar.setPassword(this.serviceName, type, token);
    }
    
    private async retrieveFromKeytar(type: string): Promise<string | null> {
        return await keytar.getPassword(this.serviceName, type);
    }
    
    // SafeStorage implementation (Electron built-in)
    private async storeWithSafeStorage(token: string, type: string): Promise<void> {
        const encrypted = safeStorage.encryptString(token);
        const filePath = this.getTokenFilePath(type);
        
        await fs.promises.writeFile(filePath, encrypted);
    }
    
    private async retrieveFromSafeStorage(type: string): Promise<string | null> {
        const filePath = this.getTokenFilePath(type);
        
        try {
            const encrypted = await fs.promises.readFile(filePath);
            return safeStorage.decryptString(encrypted);
        } catch {
            return null;
        }
    }
    
    // Encrypted file implementation (fallback)
    private async storeInEncryptedFile(token: string, type: string): Promise<void> {
        const key = this.getDerivedKey();
        const iv = crypto.randomBytes(16);
        
        const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
        
        let encrypted = cipher.update(token, 'utf8', 'hex');
        encrypted += cipher.final('hex');
        
        const authTag = cipher.getAuthTag();
        
        const data = {
            iv: iv.toString('hex'),
            authTag: authTag.toString('hex'),
            encrypted
        };
        
        const filePath = this.getTokenFilePath(type);
        await fs.promises.writeFile(filePath, JSON.stringify(data));
    }
    
    private async retrieveFromEncryptedFile(type: string): Promise<string | null> {
        const filePath = this.getTokenFilePath(type);
        
        try {
            const content = await fs.promises.readFile(filePath, 'utf8');
            const data = JSON.parse(content);
            
            const key = this.getDerivedKey();
            const iv = Buffer.from(data.iv, 'hex');
            const authTag = Buffer.from(data.authTag, 'hex');
            
            const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
            decipher.setAuthTag(authTag);
            
            let decrypted = decipher.update(data.encrypted, 'hex', 'utf8');
            decrypted += decipher.final('utf8');
            
            return decrypted;
        } catch {
            return null;
        }
    }
    
    private getDerivedKey(): Buffer {
        // Derive key from machine ID and app secret
        const machineId = require('node-machine-id').machineIdSync();
        const appSecret = process.env.APP_SECRET || 'default-secret';
        
        return crypto.pbkdf2Sync(
            appSecret,
            machineId,
            100000,
            32,
            'sha256'
        );
    }
    
    private getTokenFilePath(type: string): string {
        const userDataPath = app.getPath('userData');
        return path.join(userDataPath, 'tokens', `${type}.encrypted`);
    }
    
    async clearAll(): Promise<void> {
        const types = ['access_token', 'refresh_token', 'id_token'];
        
        for (const type of types) {
            if (this.storageMethod === 'keytar') {
                await keytar.deletePassword(this.serviceName, type);
            } else {
                const filePath = this.getTokenFilePath(type);
                try {
                    await fs.promises.unlink(filePath);
                } catch {
                    // File doesn't exist
                }
            }
        }
    }
}
```

---

## Backend Services

### Environment Variables and Secret Management

```python
# backend/security/secret_management.py
import os
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass
import boto3
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from google.cloud import secretmanager
import hvac

@dataclass
class SecretConfig:
    provider: str  # 'env', 'aws', 'azure', 'gcp', 'hashicorp'
    config: Dict[str, Any]

class SecretManager:
    """
    Unified secret management across different providers
    """
    
    def __init__(self, config: SecretConfig):
        self.config = config
        self.provider = self._init_provider()
    
    def _init_provider(self):
        """Initialize the appropriate secret provider"""
        if self.config.provider == 'env':
            return EnvironmentSecretProvider()
        elif self.config.provider == 'aws':
            return AWSSecretsManager(self.config.config)
        elif self.config.provider == 'azure':
            return AzureKeyVault(self.config.config)
        elif self.config.provider == 'gcp':
            return GCPSecretManager(self.config.config)
        elif self.config.provider == 'hashicorp':
            return HashicorpVault(self.config.config)
        else:
            raise ValueError(f"Unknown provider: {self.config.provider}")
    
    def get_secret(self, key: str) -> Optional[str]:
        """Get secret value"""
        return self.provider.get_secret(key)
    
    def set_secret(self, key: str, value: str) -> None:
        """Set secret value"""
        self.provider.set_secret(key, value)
    
    def rotate_secret(self, key: str) -> str:
        """Rotate secret and return new value"""
        return self.provider.rotate_secret(key)

class EnvironmentSecretProvider:
    """Environment variable secret provider"""
    
    def get_secret(self, key: str) -> Optional[str]:
        # Support dotenv files in development
        if os.getenv('ENVIRONMENT') == 'development':
            from dotenv import load_dotenv
            load_dotenv()
        
        return os.getenv(key)
    
    def set_secret(self, key: str, value: str) -> None:
        os.environ[key] = value
    
    def rotate_secret(self, key: str) -> str:
        # Not supported for environment variables
        raise NotImplementedError("Cannot rotate environment variables")

class AWSSecretsManager:
    """AWS Secrets Manager provider"""
    
    def __init__(self, config: Dict[str, Any]):
        self.client = boto3.client(
            'secretsmanager',
            region_name=config.get('region', 'us-east-1')
        )
        self.prefix = config.get('prefix', 'agencydark/')
    
    def get_secret(self, key: str) -> Optional[str]:
        try:
            response = self.client.get_secret_value(
                SecretId=f"{self.prefix}{key}"
            )
            
            # Handle string or binary secret
            if 'SecretString' in response:
                secret = response['SecretString']
                # Try to parse JSON
                try:
                    secret_dict = json.loads(secret)
                    return secret_dict.get(key, secret)
                except json.JSONDecodeError:
                    return secret
            else:
                # Binary secret
                return response['SecretBinary'].decode('utf-8')
                
        except self.client.exceptions.ResourceNotFoundException:
            return None
    
    def set_secret(self, key: str, value: str) -> None:
        try:
            self.client.update_secret(
                SecretId=f"{self.prefix}{key}",
                SecretString=value
            )
        except self.client.exceptions.ResourceNotFoundException:
            self.client.create_secret(
                Name=f"{self.prefix}{key}",
                SecretString=value
            )
    
    def rotate_secret(self, key: str) -> str:
        import secrets
        new_value = secrets.token_urlsafe(32)
        
        # Create new version
        self.client.put_secret_value(
            SecretId=f"{self.prefix}{key}",
            SecretString=new_value,
            VersionStages=['AWSPENDING']
        )
        
        # Promote to current
        self.client.update_secret_version_stage(
            SecretId=f"{self.prefix}{key}",
            VersionStage='AWSCURRENT',
            MoveToVersionId='AWSPENDING'
        )
        
        return new_value

class AzureKeyVault:
    """Azure Key Vault provider"""
    
    def __init__(self, config: Dict[str, Any]):
        vault_url = config.get('vault_url')
        credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=vault_url, credential=credential)
    
    def get_secret(self, key: str) -> Optional[str]:
        try:
            secret = self.client.get_secret(key)
            return secret.value
        except:
            return None
    
    def set_secret(self, key: str, value: str) -> None:
        self.client.set_secret(key, value)
    
    def rotate_secret(self, key: str) -> str:
        import secrets
        new_value = secrets.token_urlsafe(32)
        
        # Set new version
        self.client.set_secret(key, new_value)
        
        return new_value

class HashicorpVault:
    """Hashicorp Vault provider"""
    
    def __init__(self, config: Dict[str, Any]):
        self.client = hvac.Client(
            url=config.get('url', 'http://localhost:8200'),
            token=config.get('token')
        )
        self.mount_point = config.get('mount_point', 'secret')
        self.path_prefix = config.get('path_prefix', 'agencydark/')
    
    def get_secret(self, key: str) -> Optional[str]:
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=f"{self.path_prefix}{key}",
                mount_point=self.mount_point
            )
            return response['data']['data'].get(key)
        except:
            return None
    
    def set_secret(self, key: str, value: str) -> None:
        self.client.secrets.kv.v2.create_or_update_secret(
            path=f"{self.path_prefix}{key}",
            secret={key: value},
            mount_point=self.mount_point
        )
    
    def rotate_secret(self, key: str) -> str:
        import secrets
        new_value = secrets.token_urlsafe(32)
        
        self.set_secret(key, new_value)
        
        return new_value
```

---

## Encryption Strategies

### Multi-Layer Encryption

```python
# backend/security/token_encryption.py
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.backends import default_backend
import os
import base64
from typing import Tuple, Optional

class TokenEncryption:
    """
    Multi-layer token encryption
    """
    
    def __init__(self, master_key: bytes):
        self.master_key = master_key
        self.backend = default_backend()
    
    def encrypt_token(
        self,
        token: str,
        associated_data: Optional[bytes] = None
    ) -> Tuple[str, str, str]:
        """
        Encrypt token with AES-GCM
        
        Returns: (encrypted_token, nonce, tag)
        """
        # Derive encryption key
        salt = os.urandom(32)
        key = self.derive_key(self.master_key, salt)
        
        # Generate nonce
        nonce = os.urandom(12)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce),
            backend=self.backend
        )
        encryptor = cipher.encryptor()
        
        # Add associated data if provided
        if associated_data:
            encryptor.authenticate_additional_data(associated_data)
        
        # Encrypt token
        ciphertext = encryptor.update(token.encode()) + encryptor.finalize()
        
        # Get authentication tag
        tag = encryptor.tag
        
        # Encode for storage
        encrypted = base64.b64encode(salt + nonce + tag + ciphertext).decode()
        
        return encrypted
    
    def decrypt_token(
        self,
        encrypted: str,
        associated_data: Optional[bytes] = None
    ) -> str:
        """
        Decrypt token
        """
        # Decode
        data = base64.b64decode(encrypted)
        
        # Extract components
        salt = data[:32]
        nonce = data[32:44]
        tag = data[44:60]
        ciphertext = data[60:]
        
        # Derive key
        key = self.derive_key(self.master_key, salt)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce, tag),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        
        # Add associated data if provided
        if associated_data:
            decryptor.authenticate_additional_data(associated_data)
        
        # Decrypt
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        return plaintext.decode()
    
    def derive_key(self, master_key: bytes, salt: bytes) -> bytes:
        """
        Derive encryption key using PBKDF2
        """
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=self.backend
        )
        return kdf.derive(master_key)
    
    def create_token_hmac(self, token: str) -> str:
        """
        Create HMAC for token integrity
        """
        h = hmac.HMAC(self.master_key, hashes.SHA256(), backend=self.backend)
        h.update(token.encode())
        return base64.b64encode(h.finalize()).decode()
    
    def verify_token_hmac(self, token: str, token_hmac: str) -> bool:
        """
        Verify token HMAC
        """
        expected = self.create_token_hmac(token)
        provided = token_hmac
        
        # Constant-time comparison
        return hmac.compare_digest(expected, provided)
```

---

## Token Lifecycle Management

### Automatic Rotation and Cleanup

```python
# backend/security/token_lifecycle.py
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class TokenLifecycleManager:
    """
    Manage token lifecycle including rotation and cleanup
    """
    
    def __init__(self, storage, encryption):
        self.storage = storage
        self.encryption = encryption
        self.scheduler = AsyncIOScheduler()
        self.setup_scheduled_tasks()
    
    def setup_scheduled_tasks(self):
        """Setup automatic lifecycle tasks"""
        # Token cleanup every hour
        self.scheduler.add_job(
            self.cleanup_expired_tokens,
            'interval',
            hours=1,
            id='cleanup_tokens'
        )
        
        # Refresh token rotation check daily
        self.scheduler.add_job(
            self.rotate_refresh_tokens,
            'interval',
            days=1,
            id='rotate_refresh_tokens'
        )
        
        # Security audit weekly
        self.scheduler.add_job(
            self.security_audit,
            'interval',
            weeks=1,
            id='security_audit'
        )
        
        self.scheduler.start()
    
    async def cleanup_expired_tokens(self):
        """Remove expired tokens from storage"""
        logger.info("Starting token cleanup")
        
        # Get all tokens
        tokens = await self.storage.get_all_tokens()
        
        expired_count = 0
        for token_id, token_data in tokens.items():
            if self.is_expired(token_data):
                await self.storage.remove_token(token_id)
                expired_count += 1
        
        logger.info(f"Cleaned up {expired_count} expired tokens")
    
    async def rotate_refresh_tokens(self):
        """Rotate refresh tokens approaching expiration"""
        logger.info("Starting refresh token rotation")
        
        # Get refresh tokens expiring in next 7 days
        expiring_soon = await self.storage.get_tokens_expiring_soon(days=7)
        
        for token_data in expiring_soon:
            if token_data['type'] == 'refresh_token':
                await self.rotate_single_refresh_token(token_data)
    
    async def rotate_single_refresh_token(self, token_data: Dict):
        """Rotate a single refresh token"""
        try:
            # Generate new refresh token
            new_token = generate_refresh_token()
            
            # Encrypt new token
            encrypted = self.encryption.encrypt_token(new_token)
            
            # Store new token
            await self.storage.store_token(
                token_id=generate_token_id(),
                token_data={
                    'type': 'refresh_token',
                    'user_id': token_data['user_id'],
                    'client_id': token_data['client_id'],
                    'token': encrypted,
                    'created_at': datetime.utcnow(),
                    'expires_at': datetime.utcnow() + timedelta(days=30),
                    'rotated_from': token_data.get('token_id')
                }
            )
            
            # Revoke old token
            await self.storage.revoke_token(token_data['token_id'])
            
            # Notify user (optional)
            await self.notify_token_rotation(token_data['user_id'])
            
            logger.info(f"Rotated refresh token for user {token_data['user_id']}")
            
        except Exception as e:
            logger.error(f"Failed to rotate refresh token: {e}")
    
    async def security_audit(self):
        """Perform security audit on stored tokens"""
        logger.info("Starting security audit")
        
        issues = []
        
        # Check for tokens with excessive lifetime
        long_lived = await self.storage.get_tokens_with_long_lifetime(days=90)
        if long_lived:
            issues.append({
                'type': 'long_lived_tokens',
                'count': len(long_lived),
                'tokens': [t['token_id'] for t in long_lived]
            })
        
        # Check for users with excessive tokens
        user_tokens = await self.storage.get_token_count_by_user()
        for user_id, count in user_tokens.items():
            if count > 10:
                issues.append({
                    'type': 'excessive_tokens',
                    'user_id': user_id,
                    'count': count
                })
        
        # Check for suspicious patterns
        suspicious = await self.detect_suspicious_patterns()
        if suspicious:
            issues.extend(suspicious)
        
        if issues:
            await self.report_security_issues(issues)
    
    def is_expired(self, token_data: Dict) -> bool:
        """Check if token is expired"""
        expires_at = token_data.get('expires_at')
        if not expires_at:
            return False
        
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        return datetime.utcnow() > expires_at
    
    async def detect_suspicious_patterns(self) -> List[Dict]:
        """Detect suspicious token usage patterns"""
        suspicious = []
        
        # Check for tokens used from multiple IPs
        multi_ip = await self.storage.get_tokens_with_multiple_ips()
        if multi_ip:
            suspicious.append({
                'type': 'multi_ip_usage',
                'tokens': multi_ip
            })
        
        # Check for rapid token generation
        rapid_gen = await self.storage.get_rapid_token_generation()
        if rapid_gen:
            suspicious.append({
                'type': 'rapid_generation',
                'details': rapid_gen
            })
        
        return suspicious
```

---

## Security Best Practices

### Token Storage Checklist

```markdown
## Token Storage Security Checklist

### General Principles
- [ ] Never store tokens in plain text
- [ ] Use encryption at rest for all tokens
- [ ] Implement proper key management
- [ ] Use secure random generation
- [ ] Implement token expiration
- [ ] Enable token revocation
- [ ] Audit token access

### Web Applications
- [ ] Prefer memory storage for SPAs
- [ ] Use httpOnly cookies for server-rendered apps
- [ ] Never use localStorage for sensitive tokens
- [ ] Implement CSRF protection
- [ ] Use secure and sameSite cookie flags
- [ ] Implement CSP headers

### Mobile Applications
- [ ] Use OS-provided secure storage (Keychain/Keystore)
- [ ] Enable biometric protection for sensitive tokens
- [ ] Implement certificate pinning
- [ ] Obfuscate token handling code
- [ ] Use app attestation/integrity checks

### Backend Services
- [ ] Use secret management services
- [ ] Rotate secrets regularly
- [ ] Implement least privilege access
- [ ] Audit secret access
- [ ] Use hardware security modules for critical secrets
- [ ] Implement break-glass procedures

### Compliance
- [ ] Meet regulatory requirements (GDPR, HIPAA, etc.)
- [ ] Implement data residency requirements
- [ ] Enable audit logging
- [ ] Implement data retention policies
- [ ] Support right to erasure
- [ ] Document security measures
```

---

## Compliance Considerations

### Regulatory Requirements

```python
# backend/security/compliance.py
class TokenStorageCompliance:
    """
    Ensure token storage meets compliance requirements
    """
    
    @staticmethod
    def validate_gdpr_compliance(storage_method: str, location: str) -> Dict:
        """Validate GDPR compliance for token storage"""
        issues = []
        
        # Check data residency
        if location not in ['EU', 'Adequate Country']:
            issues.append("Data stored outside EU without adequate protection")
        
        # Check encryption
        if 'encrypted' not in storage_method.lower():
            issues.append("Personal data not encrypted at rest")
        
        # Check retention
        # Tokens should have defined retention periods
        
        return {
            'compliant': len(issues) == 0,
            'issues': issues
        }
    
    @staticmethod
    def validate_hipaa_compliance(storage_method: str) -> Dict:
        """Validate HIPAA compliance for token storage"""
        requirements = {
            'encryption_at_rest': True,
            'encryption_in_transit': True,
            'access_controls': True,
            'audit_logging': True,
            'automatic_logoff': True
        }
        
        # Check each requirement
        # ...
        
        return {
            'compliant': all(requirements.values()),
            'requirements': requirements
        }
```

---

## Resources

- [OWASP Token Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html#token-storage-on-client-side)
- [RFC 6819 - OAuth 2.0 Threat Model](https://tools.ietf.org/html/rfc6819#section-5.1.6)
- [Web Crypto API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API)
- [iOS Keychain Services](https://developer.apple.com/documentation/security/keychain_services)
- [Android Keystore](https://developer.android.com/training/articles/keystore)