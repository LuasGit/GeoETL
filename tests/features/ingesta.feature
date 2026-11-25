# Los datos de esta feature son ficticios y SOLO se usan en pruebas automatizadas.
Feature: Extracción rastreable y transformación Silver
  Como ingeniero de datos
  Quiero conservar la respuesta original y normalizar las observaciones
  Para reproducir una transformación sin descargar nuevamente la API

  Scenario: Un lote con una observación inválida produce solo registros válidos en Silver
    Given un lote USGS de prueba con una observación válida y otra inválida
    When almaceno Bronze y genero el dataset Silver
    Then el archivo Bronze conserva exactamente los bytes originales
    And Silver contiene una observación válida
    And se registra un rechazo por coordenada fuera de rango

  Scenario: El mismo lote con observaciones repetidas conserva una sola identidad
    Given un lote USGS de prueba con dos observaciones repetidas
    When normalizo y deduplico las observaciones
    Then solo queda una identidad de origen
