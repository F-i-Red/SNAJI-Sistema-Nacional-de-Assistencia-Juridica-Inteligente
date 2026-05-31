
export default function ProcessTimeline() {

  const eventos = [
    "Caso submetido",
    "Factos extraídos",
    "Análise constitucional",
    "Contraditório gerado",
    "Auditoria concluída"
  ];

  return (
    <div>
      <h2>Timeline Processual</h2>

      <ul>
        {eventos.map((evento, index) => (
          <li key={index}>{evento}</li>
        ))}
      </ul>
    </div>
  );
}
