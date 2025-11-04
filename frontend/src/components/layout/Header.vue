<script setup lang="ts">
import Button from 'src/components/atoms/Button.vue';
import LanguageSelector from 'src/components/atoms/LanguageSelector.vue';
</script>

<template>
  <header class="header">
    <!-- Level 1: Top -->
    <div class="header__level header__level--top">
      <!-- Left: Logo and branding -->
      <div class="header__branding">
        <img src="/epfl-logo.svg" alt="EPFL Logo" class="header__logo" />
        <h3 class="header__title">{{ $t('title') }}</h3>
      </div>
      <!-- Right: Language, info, and action buttons -->
      <div class="header__actions">
        <LanguageSelector />
        <Button icon="article" type="secondary" size="sm">
          <span>Documentation</span>
        </Button>
      </div>
    </div>

    <!-- Level 2 -->
    <!--
    <div class="header__level header__level--bottom">

      <div class="header__breadcrumb">
        <span class="header__breadcrumb-item">Home</span>
        <span class="header__breadcrumb-separator">/</span>
        <span class="header__breadcrumb-item">Infrastructure</span>
      </div>

      <div class="header__primary-action">
        <Button icon="document" type="primary" size="md">
          Validate Module
        </Button>
      </div>
    </div>
    -->
  </header>
</template>
