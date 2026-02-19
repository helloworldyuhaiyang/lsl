import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function NotFoundPage() {
  return (
    <section className="flex min-h-[70vh] items-center justify-center">
      <Card className="w-full max-w-lg bg-white/90 text-center shadow-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Page Not Found</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-slate-600">
          <p>The requested path does not exist in the current frontend skeleton.</p>
          <Button asChild>
            <Link to="/upload">Back to Upload</Link>
          </Button>
        </CardContent>
      </Card>
    </section>
  )
}
