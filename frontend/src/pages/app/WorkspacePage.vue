<template>
  <!--
    Pass-through layout for the `:unit/:year` workspace route. The workspace is
    loaded by the global `workspaceGuard`, so this page only hosts the child
    <router-view>.
  -->
  <router-view />
</template>
