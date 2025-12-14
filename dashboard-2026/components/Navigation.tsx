/**
 * Navigation Component
 * Sidebar navigation for main dashboard sections - Dark Mode
 */

'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils/cn'
import type { LucideIcon } from 'lucide-react'
import {
  Home,
  TrendingUp,
  Radio,
  Brain,
  Shield,
  FlaskConical,
  Box,
  Menu,
  Eye,
  MessageSquare,
  Activity,
  Minus,
  Clapperboard,
  Telescope,
} from 'lucide-react'
import { useState, useEffect } from 'react'

// Type-safe nav item definition
interface NavItemType {
  name: string
  href: string
  icon: LucideIcon
  description?: string
  badge?: string
}

const navigationItems: NavItemType[] = [
  {
    name: 'Overview',
    href: '/',
    icon: Eye,
    description: 'FCC Root',
  },
  {
    name: 'Market Data',
    href: '/market',
    icon: TrendingUp,
  },
  {
    name: 'Signal Feed',
    href: '/signals',
    icon: Radio,
  },
  {
    name: 'FINN Intelligence',
    href: '/finn',
    icon: Brain,
  },
  {
    name: 'System Health',
    href: '/health',
    icon: Shield,
  },
  {
    name: 'Research',
    href: '/research',
    icon: FlaskConical,
  },
  {
    name: 'Sandbox',
    href: '/sandbox',
    icon: Box,
  },
  {
    name: 'Vision-OS',
    href: '/vision-os',
    icon: Home,
  },
]

const cinematicSection: NavItemType = {
  name: 'Cinematic',
  href: '/cinematic',
  icon: Clapperboard,
  badge: 'VSV',
}

const aolSection: NavItemType = {
  name: 'Agent Observability',
  href: '/aol',
  icon: Activity,
  badge: 'AOL',
}

const skillSection: NavItemType = {
  name: 'Alpha Epistemology',
  href: '/skill',
  icon: Brain,
  badge: 'G2C',
}

// EC-018 Meta-Alpha & Freedom Optimizer
// G0 = Hypothesis Only, ZERO execution authority
const alphaDiscoverySection: NavItemType = {
  name: 'Alpha Discovery (G0)',
  href: '/alpha',
  icon: Telescope,
  badge: 'EC-018',
}

const chatSection: NavItemType = {
  name: 'Vision-Chat',
  href: '/chat',
  icon: MessageSquare,
}

export function Navigation() {
  const pathname = usePathname()

  // localStorage persistence for collapsed state
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    // Load from localStorage on mount
    const stored = localStorage.getItem('fhq-nav-collapsed')
    if (stored !== null) {
      setCollapsed(stored === 'true')
    }
  }, [])

  const handleToggleCollapse = () => {
    const newValue = !collapsed
    setCollapsed(newValue)
    localStorage.setItem('fhq-nav-collapsed', String(newValue))
  }

  return (
    <nav
      className={cn(
        'min-h-screen transition-all duration-300 relative',
        collapsed ? 'w-20' : 'w-64'
      )}
      style={{
        backgroundColor: 'hsl(var(--card))',
        borderRight: '1px solid hsl(var(--border))',
      }}
    >
      <div className="p-6">
        {/* Logo / Header */}
        <div className="flex items-center justify-between mb-8">
          {!collapsed && (
            <div>
              <h1 className="text-xl font-bold" style={{ color: 'hsl(var(--foreground))' }}>
                FHQ
              </h1>
              <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Market System
              </p>
            </div>
          )}
          <button
            onClick={handleToggleCollapse}
            className="p-2 rounded-lg transition-colors"
            style={{
              color: 'hsl(var(--muted-foreground))',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'hsl(var(--secondary))'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Items */}
        <ul className="space-y-2">
          {navigationItems.map((item) => (
            <NavItem key={item.href} item={item} pathname={pathname} collapsed={collapsed} />
          ))}
        </ul>

        {/* Cinematic Separator */}
        {!collapsed && (
          <div className="my-4 flex items-center gap-2" style={{ color: 'hsl(var(--muted-foreground) / 0.4)' }}>
            <Minus className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider">Visual Layer</span>
            <Minus className="w-4 h-4 flex-1" />
          </div>
        )}
        {collapsed && <div className="my-4 border-t" style={{ borderColor: 'hsl(var(--border))' }} />}

        {/* Cinematic Section */}
        <ul className="space-y-2">
          <NavItem item={cinematicSection} pathname={pathname} collapsed={collapsed} />
        </ul>

        {/* AOL Separator */}
        {!collapsed && (
          <div className="my-4 flex items-center gap-2" style={{ color: 'hsl(var(--muted-foreground) / 0.4)' }}>
            <Minus className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider">Agent Layer</span>
            <Minus className="w-4 h-4 flex-1" />
          </div>
        )}
        {collapsed && <div className="my-4 border-t" style={{ borderColor: 'hsl(var(--border))' }} />}

        {/* AOL Section */}
        <ul className="space-y-2">
          <NavItem item={aolSection} pathname={pathname} collapsed={collapsed} />
          <NavItem item={skillSection} pathname={pathname} collapsed={collapsed} />
        </ul>

        {/* Alpha Discovery Separator */}
        {!collapsed && (
          <div className="my-4 flex items-center gap-2" style={{ color: 'hsl(var(--muted-foreground) / 0.4)' }}>
            <Minus className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider">Discovery</span>
            <Minus className="w-4 h-4 flex-1" />
          </div>
        )}
        {collapsed && <div className="my-4 border-t" style={{ borderColor: 'hsl(var(--border))' }} />}

        {/* Alpha Discovery Section - EC-018 */}
        <ul className="space-y-2">
          <NavItem item={alphaDiscoverySection} pathname={pathname} collapsed={collapsed} />
        </ul>

        {/* Chat Separator */}
        {!collapsed && (
          <div className="my-4 flex items-center gap-2" style={{ color: 'hsl(var(--muted-foreground) / 0.4)' }}>
            <Minus className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider">Interface</span>
            <Minus className="w-4 h-4 flex-1" />
          </div>
        )}
        {collapsed && <div className="my-4 border-t" style={{ borderColor: 'hsl(var(--border))' }} />}

        {/* Chat Section */}
        <ul className="space-y-2">
          <NavItem item={chatSection} pathname={pathname} collapsed={collapsed} />
        </ul>

        {/* Footer */}
        {!collapsed && (
          <div className="absolute bottom-6 left-6 right-6">
            <div
              className="text-xs border-t pt-4"
              style={{
                color: 'hsl(var(--muted-foreground))',
                borderColor: 'hsl(var(--border))',
              }}
            >
              <p className="font-semibold" style={{ color: 'hsl(var(--foreground))' }}>
                v2.0.0
              </p>
              <p>CEO Directive 2026</p>
              <p className="mt-1 text-[10px]" style={{ color: 'hsl(var(--muted-foreground) / 0.6)' }}>
                Glass Wall | AOL
              </p>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}

function NavItem({
  item,
  pathname,
  collapsed,
}: {
  item: NavItemType
  pathname: string
  collapsed: boolean
}) {
  const Icon = item.icon
  const isActive = pathname === item.href

  return (
    <li>
      <Link
        href={item.href}
        className={cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
          'relative overflow-hidden',
          isActive ? 'nav-item-active' : 'nav-item'
        )}
        style={
          isActive
            ? {
                backgroundColor: 'hsl(var(--primary) / 0.15)',
                color: 'hsl(var(--primary))',
                fontWeight: 600,
                borderLeft: '3px solid hsl(var(--primary))',
              }
            : {
                color: 'hsl(var(--muted-foreground))',
              }
        }
        onMouseEnter={(e) => {
          if (!isActive) {
            e.currentTarget.style.backgroundColor = 'hsl(var(--secondary))'
            e.currentTarget.style.color = 'hsl(var(--foreground))'
          }
        }}
        onMouseLeave={(e) => {
          if (!isActive) {
            e.currentTarget.style.backgroundColor = 'transparent'
            e.currentTarget.style.color = 'hsl(var(--muted-foreground))'
          }
        }}
        title={collapsed ? item.name : undefined}
      >
        <Icon className="w-5 h-5 flex-shrink-0" />
        {!collapsed && <span className="flex-1">{item.name}</span>}
        {!collapsed && item.badge && (
          <span
            className="px-2 py-0.5 text-xs font-semibold rounded-full"
            style={{
              backgroundColor: 'hsl(var(--primary) / 0.2)',
              color: 'hsl(var(--primary))',
              border: '1px solid hsl(var(--primary) / 0.3)',
            }}
          >
            {item.badge}
          </span>
        )}
      </Link>
    </li>
  )
}
