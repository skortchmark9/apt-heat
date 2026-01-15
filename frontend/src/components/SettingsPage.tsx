import { useState, useEffect } from 'react';

interface Channel {
  key: string;
  current: any;
  target: any;
  last_updated: string | null;
  controllable?: boolean;
  type?: 'bool' | 'number' | 'enum' | 'string';
  options?: string[];
}

interface ChannelData {
  device_channels: Channel[];
  server_state: Channel[];
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return value.toString();
  return String(value);
}

function EditableCell({ channel, onSave }: { channel: Channel; onSave: (key: string, value: any) => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');

  const currentValue = channel.target ?? channel.current;
  const hasTarget = channel.target !== null && channel.target !== undefined;
  const mismatch = hasTarget && channel.current !== channel.target;

  const startEdit = () => {
    setValue(formatValue(currentValue));
    setEditing(true);
  };

  const saveValue = (val: any) => {
    onSave(channel.key, val);
    setEditing(false);
  };

  const cancel = () => {
    setEditing(false);
  };

  // Boolean: simple toggle or dropdown
  if (channel.type === 'bool') {
    return (
      <select
        value={currentValue ? 'true' : 'false'}
        onChange={(e) => saveValue(e.target.value === 'true')}
        className={`text-xs font-mono border rounded px-1 py-0.5 ${mismatch ? 'text-orange-600 font-bold' : 'text-blue-600'}`}
      >
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    );
  }

  // Enum: dropdown with options
  if (channel.type === 'enum' && channel.options) {
    return (
      <select
        value={currentValue ?? ''}
        onChange={(e) => saveValue(e.target.value)}
        className={`text-xs font-mono border rounded px-1 py-0.5 ${mismatch ? 'text-orange-600 font-bold' : 'text-blue-600'}`}
      >
        {channel.options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    );
  }

  // Number/string: text input
  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <input
          type={channel.type === 'number' ? 'number' : 'text'}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-16 px-1 py-0.5 text-xs font-mono border rounded"
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const parsed = channel.type === 'number' ? Number(value) : value;
              saveValue(parsed);
            }
            if (e.key === 'Escape') cancel();
          }}
          autoFocus
        />
        <button onClick={() => saveValue(channel.type === 'number' ? Number(value) : value)} className="text-green-600 text-xs">✓</button>
        <button onClick={cancel} className="text-red-600 text-xs">✕</button>
      </div>
    );
  }

  return (
    <span
      onClick={startEdit}
      className={`cursor-pointer hover:bg-blue-50 px-1 rounded ${hasTarget ? 'text-blue-600' : 'text-gray-300'} ${mismatch ? 'font-bold' : ''}`}
    >
      {formatValue(channel.target)}
    </span>
  );
}

function DeviceChannelsTable({ channels, onSetChannel }: { channels: Channel[]; onSetChannel: (key: string, value: any) => void }) {
  const controllable = channels.filter(c => c.controllable);
  const readOnly = channels.filter(c => !c.controllable);

  return (
    <div className="space-y-4">
      {/* Controllable */}
      <div>
        <h4 className="text-xs font-medium text-gray-400 mb-2">CONTROLLABLE</h4>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-1 px-2 font-medium text-gray-500 text-xs">Channel</th>
              <th className="text-left py-1 px-2 font-medium text-gray-500 text-xs">Current</th>
              <th className="text-left py-1 px-2 font-medium text-gray-500 text-xs">Target</th>
            </tr>
          </thead>
          <tbody>
            {controllable.map((ch) => {
              const mismatch = ch.target !== null && ch.target !== undefined && ch.current !== ch.target;
              return (
                <tr key={ch.key} className="border-b border-gray-100">
                  <td className="py-1.5 px-2 font-mono text-xs text-gray-700">{ch.key}</td>
                  <td className={`py-1.5 px-2 font-mono text-xs ${mismatch ? 'text-orange-600' : 'text-gray-600'}`}>
                    {formatValue(ch.current)}
                  </td>
                  <td className="py-1.5 px-2 font-mono text-xs">
                    <EditableCell channel={ch} onSave={onSetChannel} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Read-only */}
      <div>
        <h4 className="text-xs font-medium text-gray-400 mb-2">READ-ONLY</h4>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-1 px-2 font-medium text-gray-500 text-xs">Channel</th>
              <th className="text-left py-1 px-2 font-medium text-gray-500 text-xs">Value</th>
            </tr>
          </thead>
          <tbody>
            {readOnly.map((ch) => (
              <tr key={ch.key} className="border-b border-gray-100">
                <td className="py-1.5 px-2 font-mono text-xs text-gray-700">{ch.key}</td>
                <td className="py-1.5 px-2 font-mono text-xs text-gray-600">{formatValue(ch.current)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ServerStateTable({ state, onSetChannel }: { state: Channel[]; onSetChannel: (key: string, value: any) => void }) {
  const controllable = state.filter(s => s.controllable);
  const readOnly = state.filter(s => !s.controllable);

  return (
    <div className="space-y-4">
      {controllable.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-400 mb-2">CONTROLLABLE</h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-1 px-2 font-medium text-gray-500 text-xs">Key</th>
                <th className="text-left py-1 px-2 font-medium text-gray-500 text-xs">Value</th>
              </tr>
            </thead>
            <tbody>
              {controllable.map((ch) => (
                <tr key={ch.key} className="border-b border-gray-100">
                  <td className="py-1.5 px-2 font-mono text-xs text-gray-700">{ch.key}</td>
                  <td className="py-1.5 px-2 font-mono text-xs">
                    <EditableCell channel={ch} onSave={onSetChannel} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {readOnly.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-400 mb-2">READ-ONLY</h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-1 px-2 font-medium text-gray-500 text-xs">Key</th>
                <th className="text-left py-1 px-2 font-medium text-gray-500 text-xs">Value</th>
              </tr>
            </thead>
            <tbody>
              {readOnly.map((ch) => (
                <tr key={ch.key} className="border-b border-gray-100">
                  <td className="py-1.5 px-2 font-mono text-xs text-gray-700">{ch.key}</td>
                  <td className="py-1.5 px-2 font-mono text-xs text-gray-600">{formatValue(ch.target ?? ch.current)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function SettingsPage({ isActive = true }: { isActive?: boolean }) {
  const [data, setData] = useState<ChannelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchChannels = async () => {
    try {
      const res = await fetch('/api/channels');
      if (res.ok) {
        setData(await res.json());
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

  useEffect(() => {
    if (!isActive) return;
    fetchChannels();
    const interval = setInterval(fetchChannels, 5000);
    return () => clearInterval(interval);
  }, [isActive]);

  const handleSetChannel = async (key: string, value: any) => {
    try {
      const res = await fetch('/api/channels/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value }),
      });
      if (res.ok) {
        fetchChannels(); // Refresh
      }
    } catch (e) {
      console.error('Failed to set channel:', e);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-br from-gray-700 to-gray-900 text-white px-6 pt-6 pb-8">
        <div className="text-3xl font-bold">Settings</div>
      </div>

      <div className="px-6 -mt-4">
        {loading ? (
          <div className="bg-white rounded-2xl p-5 shadow-sm text-gray-400 text-center">Loading...</div>
        ) : error ? (
          <div className="bg-white rounded-2xl p-5 shadow-sm text-red-500 text-center">{error}</div>
        ) : data && (
          <>
            {/* Device Channels */}
            <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
              <h3 className="text-sm font-medium text-gray-500 mb-4">Device Channels</h3>
              <DeviceChannelsTable channels={data.device_channels} onSetChannel={handleSetChannel} />
              <p className="text-xs text-gray-400 mt-4">
                Click target value to edit. <span className="text-orange-600">Orange</span> = pending change.
              </p>
            </div>

            {/* Server State */}
            <div className="bg-white rounded-2xl p-5 shadow-sm mb-4">
              <h3 className="text-sm font-medium text-gray-500 mb-4">Server State</h3>
              <ServerStateTable state={data.server_state} onSetChannel={handleSetChannel} />
            </div>
          </>
        )}
      </div>

      {/* Bottom spacer for nav */}
      <div className="h-24" />
    </div>
  );
}
