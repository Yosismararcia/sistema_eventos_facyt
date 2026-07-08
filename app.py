from flask import Flask, render_template

app = Flask(__name__)

# Ruta principal: Cuando alguien entre a la app, verá el index.html
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    # El modo debug permite ver cambios en tiempo real sin reiniciar el servidor
    app.run(debug=True)