# CryptoTicker

Real-time cryptocurrency futures price tracker with a rich terminal UI. Streams live data from Binance Futures WebSocket.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  ⚡ BINANCE FUTURES   │   ● LIVE   │   ⣾                                    ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  BTC/USDT  PERPETUAL                                                         ║
║  2026-03-18  14:23:45                                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   ███  ████   ███      ██  ██  █████  ██                                     ║
║   █ █  █  █     █      ██ █   █       ██                                     ║
║   ███  ████   ██   ██  ██     █████   ██                                     ║
║   █ █     █  █        ██     █   █  ██                                       ║
║   ███  ████  █████  ██ ██    █████  ██                                       ║
║                                                                              ║
║  ▲ +2.34%  ($1,923.45 24h)                                                   ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Bid: $83,244.50  │  Ask: $83,245.50  (spread: 0.0012%)                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  24h Range:                                                                  ║
║  [████████████████████████▌░░░░░░░░░░] 72.3%                                ║
║  Lo: $81,321.00   │   Hi: $85,467.00                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Price trend: ▂▃▃▄▅▆▆▇▇█▇▆▅▅▆▇████▇▇▆▇█                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Volume (USDT)  $24.87B                                                      ║
║  Volume ( BTC)  $298.5K                                                      ║
║  Trades (24h)   1.2M                                                         ║
║  Open Price     $82,100.34                                                   ║
║  VWAP (24h)     $83,012.56                                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  fstream.binance.com  │  Press Ctrl+C to exit                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

## Features

- **Large ASCII price display** - Current price rendered as 5-line-tall block characters, color-coded green/red
- **Real-time streaming** - WebSocket connection to Binance Futures for instant updates
- **24h statistics** - Change %, high/low range, volume, trade count, VWAP, open price
- **Bid/Ask spread** - Live best bid and ask prices with spread percentage
- **Price range bar** - Visual position indicator within the 24h high/low range
- **Sparkline chart** - Miniature price trend visualization from recent ticks
- **Auto-reconnection** - Exponential backoff reconnection on connection drops
- **Cross-platform** - Works on Windows, macOS, and Linux
- **Smart symbol input** - Accepts `btc`, `BTC`, `btcusdt`, `BTCUSDT`, `btcusdt.p`, `bitcoin`, etc.
- **Flicker-free rendering** - Cursor-home + overwrite approach eliminates screen flash
- **Compact mode** - Single-line price display for smaller terminals

## Installation

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/cryptoticker.git
cd cryptoticker

# Install dependencies
pip install -r requirements.txt

# Run
python cryptoticker.py btc
```

### Install as CLI Tool

```bash
pip install .
cryptoticker btc
```

## Usage

```bash
# Interactive mode (prompts for symbol)
python cryptoticker.py

# Track specific coins
python cryptoticker.py btc
python cryptoticker.py eth
python cryptoticker.py sol
python cryptoticker.py doge

# Accepts various formats
python cryptoticker.py BTCUSDT
python cryptoticker.py btcusdt.p
python cryptoticker.py BTC/USDT
python cryptoticker.py bitcoin

# Compact mode (single-line price)
python cryptoticker.py btc --compact

# Disable colors
python cryptoticker.py btc --no-color

# Debug logging to file
python cryptoticker.py btc --log-file debug.log

# Show version
python cryptoticker.py --version
```

## Requirements

- Python 3.8+
- `websocket-client` - WebSocket connection to Binance
- `colorama` - (Windows only, auto-installed) ANSI color support

## Supported Symbols

Any Binance Futures perpetual contract. Common examples:

| Input | Tracked Symbol |
|-------|---------------|
| `btc` | BTCUSDT |
| `eth` | ETHUSDT |
| `sol` | SOLUSDT |
| `doge` | DOGEUSDT |
| `xrp` | XRPUSDT |
| `bitcoin` | BTCUSDT |
| `ethereum` | ETHUSDT |
| `btcusdt.p` | BTCUSDT |
| `BTC/USDT` | BTCUSDT |

## How It Works

1. Connects to Binance Futures WebSocket (`wss://fstream.binance.com/ws/<symbol>@ticker`)
2. Receives real-time 24h ticker updates (~250ms interval)
3. Renders a full-screen terminal UI with market data
4. Auto-reconnects on disconnection with exponential backoff

## License

MIT License - see [LICENSE](LICENSE) for details.
