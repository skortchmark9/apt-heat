import { useState, useEffect } from 'react';

interface Channel {
  key: string;
  current: any;
  target: any;
  last_updated: string | null;
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return value.toString();
  return String(value);
}

function ChannelTable() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchChannels = async () => {
      try {
        const res = await fetch('/api/channels');
        if (res.ok) {
          const data = await res.json();
          setChannels(data.channels);
          setError(null);
        } else {
          setError('Failed to fetch channels');
        }
      } catch (e) {
        setError('Connection error');
      } finally {
        setLoading(false);
      }
    };

    fetchChannels();
    const interval = setInterval(fetchChannels, 2000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div className="text-gray-400 text-center py-8">Loading channels...</div>;
  }

  if (error) {
    return <div className="text-red-500 text-center py-8">{error}</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 px-2 font-medium text-gray-500">Channel</th>
            <th className="text-left py-2 px-2 font-medium text-gray-500">Current</th>
            <th className="text-left py-2 px-2 font-medium text-gray-500">Target</th>
          </tr>
        </thead>
        <tbody>
          {channels.map((ch) => {
            const hasTarget = ch.target !== null && ch.target !== undefined;
            const mismatch = hasTarget && ch.current !== ch.target;

            return (
              <tr key={ch.key} className="border-b border-gray-100">
                <td className="py-2 px-2 font-mono text-xs text-gray-700">{ch.key}</td>
                <td className={`py-2 px-2 font-mono text-xs ${mismatch ? 'text-orange-600' : 'text-gray-600'}`}>
                  {formatValue(ch.current)}
                </td>
                <td className={`py-2 px-2 font-mono text-xs ${hasTarget ? 'text-blue-600' : 'text-gray-300'}`}>
                  {formatValue(ch.target)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function SettingsPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-br from-gray-700 to-gray-900 text-white px-6 pt-6 pb-8">
        <div className="text-3xl font-bold">Settings</div>
      </div>

      <div className="px-6 -mt-4">
        {/* Channel Status */}
        <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
          <h3 className="text-sm font-medium text-gray-500 mb-4">Channel Status</h3>
          <ChannelTable />
          <p className="text-xs text-gray-400 mt-4">
            <span className="text-orange-600">Orange</span> = current differs from target
          </p>
        </div>
      </div>

      {/* Bottom spacer for nav */}
      <div className="h-24" />
    </div>
  );
}
