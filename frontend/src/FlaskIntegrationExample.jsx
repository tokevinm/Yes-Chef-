import React, { useState, useEffect } from 'react'

const FlaskIntegrationExample = () => {
  const [data, setData] = useState('')

  useEffect(() => {
    fetch('/api/data')
      .then(response => response.json())
      .then(data => setData(data.message))
  }, [])

  return (
    <div className="container mt-5">
      <h2>React + Flask Integration Example</h2>
      <p>Data from Flask: {data}</p>
    </div>
  )
}

export default FlaskIntegrationExample