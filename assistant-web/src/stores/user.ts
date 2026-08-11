import { defineStore } from 'pinia';

export const useUserStore = defineStore('user', {
  state: () => ({
    username: '',
    userId: 0,
    role: '',
  }),
  actions: {
    setUsername(name: string) {
      this.username = name;
    },
    setUserId(id: number) {
      this.userId = id;
    },
    setRole(role: string) {
      this.role = role;
    }
  }
});
