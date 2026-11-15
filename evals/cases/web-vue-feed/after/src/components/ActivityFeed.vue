<template>
  <section class="feed">
    <div class="toolbar" v-once>
      <strong>Last 24 hours</strong>
    </div>
    <input v-model="search" placeholder="Filter by actor or resource" />
    <label><input type="checkbox" v-model="hideLogins" /> Hide logins</label>
    <p>{{ matching.length }} events · {{ deletes }} deletes</p>

    <ul class="rows" :style="{ height: `${listHeight}px` }">
      <li v-for="event in matching" v-if="!(hideLogins && event.action === 'login')" :key="event.id"
          v-memo="[event.id, selectedId === event.id]" :class="{ selected: selectedId === event.id }"
          @click="selectedId = event.id">
        <time>{{ formatTime(event.at) }}</time> {{ event.actor }} {{ event.action }} {{ event.resource }}
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { fetchEvents, type ActivityEvent } from "../api";

const events = ref<ActivityEvent[]>([]);
const search = ref("");
const hideLogins = ref(false);
const selectedId = ref<number | null>(null);
const listHeight = ref(window.innerHeight - 160);
const deletes = ref(0);

const timeFormat = new Intl.DateTimeFormat("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const formatTime = (iso: string) => timeFormat.format(new Date(iso));

// Newest first, filtered by the search box.
const matching = computed(() => {
  const q = search.value.toLowerCase();
  return events.value
    .sort((a, b) => b.at.localeCompare(a.at))
    .filter((e) => !q || e.actor.toLowerCase().includes(q) || e.resource.toLowerCase().includes(q));
});

// Keep the delete counter in sync with the data.
watch(events, (list) => {
  deletes.value = list.filter((e) => e.action === "delete").length;
}, { deep: true });

function onResize() {
  listHeight.value = window.innerHeight - 160;
}

onMounted(async () => {
  window.addEventListener("resize", onResize);
  events.value = await fetchEvents();
});
</script>
