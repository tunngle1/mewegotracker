FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set Python path so 'bot' module is found
ENV PYTHONPATH=/app

# Run the bot
CMD ["python", "-m", "bot.main"]
