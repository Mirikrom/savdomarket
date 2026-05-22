import { createRouter, createWebHistory } from 'vue-router'

const ForgotPasswordView = () => import('../views/auth/ForgotPasswordView.vue')
const LoginView = () => import('../views/auth/LoginView.vue')
const RegisterView = () => import('../views/auth/RegisterView.vue')

const AppLayout = () => import('../components/AppLayout.vue')
const DashboardView = () => import('../views/DashboardView.vue')
const CategoriesView = () => import('../views/catalog/CategoriesView.vue')
const ProductsView = () => import('../views/catalog/ProductsView.vue')
const InventoryView = () => import('../views/inventory/InventoryView.vue')
const StockMovementsView = () => import('../views/inventory/StockMovementsView.vue')
const StockReceiptView = () => import('../views/inventory/StockReceiptView.vue')
const StockAdjustmentView = () => import('../views/inventory/StockAdjustmentView.vue')
const PosView = () => import('../views/sales/PosView.vue')
const SalesHistoryView = () => import('../views/sales/SalesHistoryView.vue')
const DebtorsView = () => import('../views/sales/DebtorsView.vue')
const UsersView = () => import('../views/settings/UsersView.vue')
const BranchesView = () => import('../views/settings/BranchesView.vue')
const BillingView = () => import('../views/settings/BillingView.vue')
const ReportsView = () => import('../views/reports/ReportsView.vue')

const ProviderLayout = () => import('../components/ProviderLayout.vue')
const ProviderDashboardView = () => import('../views/provider/ProviderDashboardView.vue')
const ProviderOrganizationsView = () =>
  import('../views/provider/ProviderOrganizationsView.vue')
const ProviderOrganizationDetailView = () =>
  import('../views/provider/ProviderOrganizationDetailView.vue')
const ProviderPlansView = () => import('../views/provider/ProviderPlansView.vue')
const ProviderMijozlarView = () => import('../views/provider/ProviderMijozlarView.vue')
const ProviderSettingsView = () => import('../views/provider/ProviderSettingsView.vue')

const routes = [
  { path: '/', redirect: '/app' },
  {
    path: '/auth/login',
    name: 'login',
    component: LoginView,
    meta: { guestOnly: true },
  },
  {
    path: '/auth/register',
    name: 'register',
    component: RegisterView,
    meta: { guestOnly: true },
  },
  {
    path: '/auth/forgot-password',
    name: 'forgot-password',
    component: ForgotPasswordView,
    meta: { guestOnly: true },
  },
  { path: '/auth/reset-password', redirect: '/auth/forgot-password' },
  {
    path: '/app',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'dashboard', component: DashboardView },
      { path: 'products', name: 'products', component: ProductsView, meta: { sellerAllowed: true } },
      { path: 'categories', name: 'categories', component: CategoriesView, meta: { sellerAllowed: true } },
      { path: 'inventory', name: 'inventory', component: InventoryView },
      { path: 'inventory/movements', name: 'inventory-movements', component: StockMovementsView },
      {
        path: 'inventory/receipt',
        name: 'inventory-receipt',
        component: StockReceiptView,
        meta: { sellerAllowed: true },
      },
      { path: 'inventory/adjust', name: 'inventory-adjust', component: StockAdjustmentView },
      { path: 'pos', name: 'pos', component: PosView, meta: { sellerAllowed: true } },
      { path: 'sales', name: 'sales-history', component: SalesHistoryView, meta: { sellerAllowed: true } },
      { path: 'debtors', name: 'debtors', component: DebtorsView, meta: { sellerAllowed: true } },
      { path: 'users', name: 'users', component: UsersView },
      { path: 'branches', name: 'branches', component: BranchesView },
      { path: 'billing', name: 'billing', component: BillingView },
      { path: 'reports', name: 'reports', component: ReportsView },
    ],
  },
  {
    path: '/provider',
    component: ProviderLayout,
    meta: { requiresAuth: true, providerOnly: true },
    children: [
      { path: '', name: 'provider-dashboard', component: ProviderDashboardView },
      { path: 'orgs', name: 'provider-orgs', component: ProviderOrganizationsView },
      {
        path: 'orgs/:id',
        name: 'provider-org-detail',
        component: ProviderOrganizationDetailView,
      },
      { path: 'plans', name: 'provider-plans', component: ProviderPlansView },
      {
        path: 'mijozlar',
        name: 'provider-mijozlar',
        component: ProviderMijozlarView,
      },
      { path: 'users', redirect: '/provider/mijozlar' },
      { path: 'settings', name: 'provider-settings', component: ProviderSettingsView },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  const isProvider = localStorage.getItem('is_provider') === '1'

  if (to.meta.requiresAuth && !token) return { name: 'login' }
  if (to.meta.guestOnly && token) {
    return isProvider ? { name: 'provider-dashboard' } : { name: 'dashboard' }
  }

  // Provider zonasiga faqat superuser kira oladi.
  if (to.meta.providerOnly && token && !isProvider) {
    return { name: 'dashboard' }
  }

  // Superuser /app zonasiga kirsa, /provider'ga yo'naltiramiz (impersonate qilmagan bo'lsa).
  if (
    isProvider &&
    (to.path === '/app' || to.path.startsWith('/app/')) &&
    !to.query.from_provider
  ) {
    // Avtomatik yo'naltirishni faqat boshlang'ich kirishda qilamiz, qo'lda
    // o'tishni cheklashmaymiz — buning uchun localStorage `prov_active` ni
    // tekshiramiz. Hozir oddiy redirect qilamiz.
    // (Owner sifatida kirish — impersonate — is_provider'ni o'chiradi.)
    // return { name: 'provider-dashboard' }
  }

  // Sotuvchi faqat ruxsat etilgan sahifalarga kirsin.
  if (to.path.startsWith('/app/') || to.path === '/app') {
    try {
      const cached = localStorage.getItem('user_role')
      if (cached === 'seller' && !to.meta.sellerAllowed) {
        return { name: 'pos' }
      }
      // Eski kassir/moderator akkauntlari migratsiyadan keyin seller bo‘ladi
      if (
        (cached === 'cashier' || cached === 'moderator' || cached === 'admin') &&
        !to.meta.sellerAllowed
      ) {
        return { name: 'pos' }
      }
    } catch {
      /* ignore */
    }
  }
  return true
})

export default router
